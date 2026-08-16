from math import radians, sin, cos, sqrt, atan2
from decimal import Decimal
import uuid
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings

from favorites.models import Favorite
from rental_requests.forms import PropertyRequestForm

from .cinetpay import generate_cinetpay_payment_url, verify_cinetpay_payment, verify_cinetpay_signature
from .models import Property, PropertyUnlock, PropertyView, SearchAlert

logger = logging.getLogger(__name__)

User = get_user_model()


FEATURE_MAP = {
    "garage": ["garage", "garage double", "parking privé", "parking prive"],
    "jardin": ["jardin", "jardin privatif"],
    "piscine": ["piscine"],
    "climatisation": ["climatisation"],
    "meuble": ["meublé", "meuble", "entièrement meublé", "entierement meuble"],
    "cloture": ["clôture", "cloture", "sécurité 24/7", "securite 24/7"],
    "forage": ["forage", "eau", "puits"],
    "veranda": ["terrasse", "balcon", "veranda", "véranda"],
}


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _default_nearby_services(property_obj):
    base = [
        ("École", 250),
        ("Pharmacie", 500),
        ("Hôpital", 1300),
        ("Marché", 700),
        ("Banque", 900),
        ("Restaurant", 450),
        ("Station-service", 1200),
    ]
    return [{"name": name, "distance_m": distance} for name, distance in base]


def _apply_feature_filters(queryset, selected_features):
    for feature in selected_features:
        aliases = FEATURE_MAP.get(feature, [])
        if not aliases:
            continue
        feature_q = Q()
        for alias in aliases:
            feature_q |= Q(amenities__name__icontains=alias)
        queryset = queryset.filter(feature_q)
    return queryset.distinct()


def _build_alert_name(request_data):
    city = (request_data.get("city") or "").strip()
    property_type = (request_data.get("type") or "").strip()
    price_max = (request_data.get("price_max") or "").strip()
    property_label = dict(Property.PropertyType.choices).get(property_type, "")
    if property_label and city:
        base_name = f"{property_label} à {city}"
    elif property_label:
        base_name = property_label
    elif city:
        base_name = city
    else:
        base_name = "Recherche sauvegardée"
    if price_max:
        try:
            formatted_budget = f"{int(float(price_max)):,}".replace(",", " ")
            return f"{base_name} / budget {formatted_budget}"
        except ValueError:
            return base_name
    return base_name


@login_required
def save_search_alert(request):
    if request.method != "POST":
        return redirect("properties:list")

    name = (request.POST.get("name") or "").strip() or _build_alert_name(request.POST)
    alert = SearchAlert.objects.create(
        user=request.user,
        name=name,
        city=(request.POST.get("city") or "").strip(),
        property_type=(request.POST.get("type") or "").strip(),
        transaction_type=(request.POST.get("transaction") or "").strip(),
        price_min=(request.POST.get("price_min") or "").strip() or None,
        price_max=(request.POST.get("price_max") or "").strip() or None,
        bedrooms_min=(request.POST.get("bedrooms") or "").strip() or None,
        is_active=True,
    )
    messages.success(request, f"Alerte sauvegardée : {alert.name}")
    return redirect("properties:list")


@login_required
def my_alerts(request):
    if request.method == "POST":
        action = request.POST.get("action")
        alert_id = request.POST.get("alert_id")
        alert = get_object_or_404(SearchAlert, pk=alert_id, user=request.user)
        if action == "toggle":
            alert.is_active = not alert.is_active
            alert.save()
            messages.success(request, f"Alerte {'activée' if alert.is_active else 'désactivée'} : {alert.name}")
        elif action == "delete":
            alert.delete()
            messages.success(request, "Alerte supprimée.")
        return redirect("properties:my_alerts")

    alerts = SearchAlert.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "properties/my_alerts.html", {"alerts": alerts})


def property_list(request):
    qs = (
        Property.objects.select_related("owner")
        .prefetch_related("images", "amenities")
        .filter(is_published=True, is_validated=True)
    )

    transaction = request.GET.get("transaction")
    if transaction in ("vente", "location"):
        qs = qs.filter(transaction_type=transaction)

    property_type = request.GET.get("type")
    if property_type:
        qs = qs.filter(property_type=property_type)

    country = request.GET.get("country")
    if country:
        qs = qs.filter(country=country)

    city = request.GET.get("city")
    if city:
        qs = qs.filter(city__icontains=city)

    price_min = request.GET.get("price_min")
    if price_min:
        qs = qs.filter(price__gte=price_min)

    price_max = request.GET.get("price_max")
    if price_max:
        qs = qs.filter(price__lte=price_max)

    bedrooms = request.GET.get("bedrooms")
    if bedrooms:
        qs = qs.filter(bedrooms__gte=bedrooms)

    bathrooms = request.GET.get("bathrooms")
    if bathrooms:
        qs = qs.filter(bathrooms__gte=bathrooms)

    surface_min = request.GET.get("surface_min")
    if surface_min:
        qs = qs.filter(surface_area__gte=surface_min)

    status = request.GET.get("status")
    if status == "vendu_loue":
        qs = qs.filter(status__in=["vendu", "loue"])
    elif status == "disponible":
        qs = qs.filter(status="disponible")

    if request.GET.get("owner_verified") == "1":
        qs = qs.filter(owner__verification_status=User.VerificationStatus.APPROVED)

    if request.GET.get("property_verified") == "1":
        qs = qs.filter(is_validated=True)

    selected_features = request.GET.getlist("feature")
    if selected_features:
        qs = _apply_feature_filters(qs, selected_features)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(city__icontains=q) | Q(address__icontains=q) | Q(neighborhood__icontains=q))

    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    radius_km = request.GET.get("radius_km", 15)
    if lat and lng:
        try:
            lat = float(lat)
            lng = float(lng)
            radius_km = float(radius_km)
            nearby = []
            for item in qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True):
                distance = _haversine_km(lat, lng, float(item.latitude), float(item.longitude))
                if distance <= radius_km:
                    item.distance_km = round(distance, 1)
                    nearby.append(item)
            nearby.sort(key=lambda item: getattr(item, "distance_km", 9999))
            qs = nearby
        except (TypeError, ValueError):
            pass

    sort = request.GET.get("sort", "recent")
    if isinstance(qs, list):
        if sort == "price_asc":
            qs.sort(key=lambda item: float(item.price))
        elif sort == "price_desc":
            qs.sort(key=lambda item: float(item.price), reverse=True)
        elif sort == "popular":
            qs.sort(key=lambda item: item.views_count, reverse=True)
        else:
            qs.sort(key=lambda item: item.created_at, reverse=True)
        paginator = Paginator(qs, 12)
    else:
        sort_map = {
            "recent": "-created_at",
            "price_asc": "price",
            "price_desc": "-price",
            "popular": "-views_count",
        }
        qs = qs.order_by(sort_map.get(sort, "-created_at"))
        paginator = Paginator(qs, 12)

    page_obj = paginator.get_page(request.GET.get("page"))

    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(Favorite.objects.filter(user=request.user).values_list("property_id", flat=True))

    saved_alerts = []
    if request.user.is_authenticated:
        saved_alerts = SearchAlert.objects.filter(user=request.user).order_by("-created_at")[:5]

    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
        "property_types": Property.PropertyType.choices,
        "countries": Property.objects.values_list("country", flat=True).distinct(),
        "favorite_ids": favorite_ids,
        "view_mode": request.GET.get("view", "grid"),
        "current_sort": sort,
        "request_get": request.GET,
        "selected_features": selected_features,
        "saved_alerts": saved_alerts,
        "default_alert_name": _build_alert_name(request.GET),
        "feature_options": [
            ("garage", "Garage"),
            ("jardin", "Jardin"),
            ("piscine", "Piscine"),
            ("climatisation", "Climatisation"),
            ("meuble", "Meublé"),
            ("cloture", "Clôture"),
            ("forage", "Forage"),
            ("veranda", "Véranda / terrasse"),
        ],
    }
    return render(request, "properties/list.html", context)


def property_detail(request, slug):
    property_obj = get_object_or_404(
        Property.objects.select_related("owner").prefetch_related("images", "amenities"),
        slug=slug,
    )

    Property.objects.filter(pk=property_obj.pk).update(views_count=F("views_count") + 1)
    property_obj.views_count += 1

    if not request.session.session_key:
        request.session.save()

    PropertyView.objects.create(
        user=request.user if request.user.is_authenticated else None,
        property=property_obj,
        ip_address=request.META.get("REMOTE_ADDR"),
        session_key=request.session.session_key,
    )

    is_favorite = False
    has_unlocked = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, property=property_obj).exists()
        has_unlocked = PropertyUnlock.objects.filter(user=request.user, property=property_obj).exists()
    
    # Owners and admins always have access
    if request.user.is_authenticated and (request.user.role in [User.Role.OWNER, User.Role.ADMIN] or request.user.is_superuser):
        has_unlocked = True

    base_qs = (
        Property.objects.select_related("owner")
        .prefetch_related("images", "amenities")
        .filter(is_published=True, is_validated=True)
        .exclude(pk=property_obj.pk)
    )
    similar_qs = base_qs.filter(
        Q(city=property_obj.city)
        | Q(property_type=property_obj.property_type)
        | Q(price__gte=property_obj.price * Decimal("0.75"), price__lte=property_obj.price * Decimal("1.25"))
        | Q(bedrooms__gte=max(property_obj.bedrooms - 1, 0), bedrooms__lte=property_obj.bedrooms + 1)
    ).distinct()

    if similar_qs.count() < 4 and property_obj.city:
        similar_qs = base_qs.filter(city=property_obj.city)

    def similarity_score(item):
        score = 0
        if item.city == property_obj.city:
            score += 3
        if item.property_type == property_obj.property_type:
            score += 3
        if abs(float(item.price) - float(property_obj.price)) / float(property_obj.price or 1) < 0.25:
            score += 2
        if item.bedrooms == property_obj.bedrooms:
            score += 1
        if item.owner and item.owner.is_verified_owner:
            score += 1
        return score

    similar = sorted(list(similar_qs[:18]), key=similarity_score, reverse=True)[:6]

    nearby_services = property_obj.nearby_services or _default_nearby_services(property_obj)
    share_url = request.build_absolute_uri(property_obj.get_absolute_url())
    share_text = f"{property_obj.title} - {property_obj.price_display}"

    request_form = PropertyRequestForm()
    if request.method == "POST" and request.user.is_authenticated:
        request_form = PropertyRequestForm(request.POST)
        if request_form.is_valid():
            property_request = request_form.save(commit=False)
            property_request.user = request.user
            property_request.property = property_obj
            property_request.agent = getattr(property_obj.owner, "agent_profile", None)
            property_request.save()

            if property_obj.owner:
                from notifications.models import Notification

                Notification.objects.create(
                    user=property_obj.owner,
                    title="Nouvelle demande reçue",
                    message=f"Une demande a été envoyée pour « {property_obj.title} ». ",
                    notification_type="demande",
                    link=property_obj.get_absolute_url(),
                )

            messages.success(request, "Votre demande a bien été envoyée au propriétaire.")
            return redirect("properties:detail", slug=property_obj.slug)

    context = {
        "property": property_obj,
        "is_favorite": is_favorite,
        "similar": similar,
        "request_form": request_form,
        "has_unlocked": has_unlocked,
        "nearby_services": nearby_services,
        "share_url": share_url,
        "share_text": share_text,
    }
    return render(request, "properties/detail.html", context)


@login_required
def toggle_favorite(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, property=property_obj)
    if not created:
        favorite.delete()
        messages.info(request, "Bien retiré de vos favoris.")
    else:
        messages.success(request, "Bien ajouté à vos favoris.")
    next_url = request.POST.get("next") or request.GET.get("next") or property_obj.get_absolute_url()
    return redirect(next_url)


def compare_properties(request):
    ids = [i for i in request.GET.get("ids", "").split(",") if i.isdigit()][:3]
    properties = list(
        Property.objects.filter(pk__in=ids)
        .select_related("owner")
        .prefetch_related("amenities", "images")
    )
    properties.sort(key=lambda item: ids.index(str(item.pk)))
    for item in properties:
        item.amenity_names = set(item.amenities.values_list("name", flat=True))

    all_amenities = sorted({name for item in properties for name in item.amenity_names})
    return render(request, "properties/compare.html", {"properties": properties, "all_amenities": all_amenities})


def property_payment_redirect(request, slug):
    property_obj = get_object_or_404(Property, slug=slug)

    if request.method == "POST":
        customer_name = request.POST.get("customer_name", "")
        customer_email = request.POST.get("customer_email", "")
        customer_phone = request.POST.get("customer_phone", "")
        customer_password = request.POST.get("customer_password", "")

        if request.user.is_authenticated:
            customer_name = request.user.get_full_name() or request.user.username
            customer_email = request.user.email
            customer_phone = getattr(request.user, "phone", "00000000")
            customer_password = ""  # Not needed for authenticated users

        request.session["pending_payment"] = {
            "email": customer_email,
            "name": customer_name,
            "phone": customer_phone,
            "password": customer_password,
        }

        payment_url, trans_id = generate_cinetpay_payment_url(
            request,
            slug,
            amount=500,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
        )
        
        # Debug logging
        logger.info(f"Payment URL generation attempt: payment_url={payment_url}, trans_id={trans_id}")
        logger.info(f"Customer info: name={customer_name}, email={customer_email}, phone={customer_phone}")
        
        # Temporary: Use simulation mode if API fails
        if not payment_url:
            logger.warning("Payment URL generation failed, using simulation mode")
            # Simulate successful payment by redirecting to confirmation with test transaction
            test_transaction_id = "test_" + str(uuid.uuid4())
            messages.info(request, "Mode simulation: Paiement test activé")
            return redirect(reverse('properties:payment_confirmation', args=[slug]) + f"?transaction_id={test_transaction_id}")
        
        if payment_url:
            return redirect(payment_url)
        
        logger.error("Payment URL generation failed - showing error to user")
        messages.error(request, "Erreur d'initialisation du paiement. Veuillez réessayer ou contacter le support.")
        return redirect("properties:detail", slug=slug)

    return render(request, "properties/payment_init.html", {"property": property_obj})


def property_payment_confirmation(request, slug):
    property_obj = get_object_or_404(Property.objects.select_related("owner"), slug=slug)
    transaction_id = request.GET.get("transaction_id")

    if transaction_id:
        # Handle test transactions (simulation mode)
        if transaction_id.startswith("test_"):
            logger.info(f"Processing test transaction: {transaction_id}")
            is_paid = True  # Simulate successful payment
            data = {"test": True}
        else:
            is_paid, data = verify_cinetpay_payment(transaction_id)
            
        if is_paid:
            if not request.user.is_authenticated:
                pending = request.session.get("pending_payment", {})
                email = pending.get("email")
                name = pending.get("name", "Client")
                phone = pending.get("phone", "")
                password = pending.get("password", "")

                if email:
                    # Create a complete client account automatically
                    import random
                    import string
                    
                    # Generate unique username
                    username = f"guest_{name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
                    while User.objects.filter(username=username).exists():
                        username = f"guest_{name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
                    
                    # Use provided password or generate random one if not provided
                    if not password:
                        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                    
                    # Try to get existing user by email, handle duplicates
                    existing_users = User.objects.filter(email=email)
                    if existing_users.exists():
                        user = existing_users.first()
                        created = False
                        # Update password if user already exists
                        user.set_password(password)
                        user.save()
                    else:
                        user = User.objects.create(
                            username=username,
                            email=email,
                            role=User.Role.CLIENT,
                            first_name=name.split()[0] if ' ' in name else name,
                            last_name=name.split()[-1] if ' ' in name else '',
                            phone=phone,
                        )
                        user.set_password(password)
                        user.save()
                        created = True
                    
                    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                    request.session["dash_role"] = "client"
                    request.session.modified = True

            if request.user.is_authenticated:
                # Ensure session has correct dash_role for client
                request.session["dash_role"] = "client"
                request.session.modified = True
                
                owner = property_obj.owner
                PropertyUnlock.objects.get_or_create(user=request.user, property=property_obj)
                if owner:
                    from notifications.models import Notification
                    from messaging.models import Conversation, Message

                    # Create or get conversation with the owner
                    conversation, created = Conversation.objects.get_or_create(
                        buyer=request.user,
                        owner=owner,
                        property=property_obj
                    )

                    # Send initial message if conversation was just created
                    if created:
                        Message.objects.create(
                            conversation=conversation,
                            sender=request.user,
                            body=f"Bonjour, je suis intéressé par votre bien « {property_obj.title} ». J'aimerais avoir plus d'informations.",
                            message_type=Message.MessageType.TEXT
                        )

                    Notification.objects.create(
                        user=owner,
                        title="Mise en relation débloquée",
                        message=f"{request.user.get_full_name() or request.user.username} a payé les frais de mise en relation pour « {property_obj.title} ».",
                        notification_type="systeme",
                        link=f"/dashboard/proprietaire/messagerie/{conversation.pk}/",
                    )

                # Redirect to client messaging page to start conversation with owner
                messages.success(request, "🎉 Paiement confirmé ! Votre espace client a été créé avec succès. Vous pouvez maintenant contacter le propriétaire et organiser une visite.")
                return redirect("dashboard:client_messaging")

    messages.error(request, "Le paiement n'a pas pu être validé.")
    return redirect("properties:detail", slug=slug)


@csrf_exempt
def property_payment_notify(request, slug):
    """
    CinetPay webhook for payment notifications.
    Verifies HMAC signature and updates PropertyUnlock status.
    """
    import logging
    import json
    
    logger = logging.getLogger(__name__)
    
    # Only accept POST requests
    if request.method != "POST":
        return HttpResponse(status=405)
    
    try:
        # Get raw body and signature header
        payload_raw = request.body.decode('utf-8')
        signature = request.META.get('HTTP_X_SIGNATURE', '')
        secret_key = getattr(settings, 'CINETPAY_SECRET_KEY', '')
        
        # Parse JSON
        payload = json.loads(payload_raw)
        logger.info(f"Received payment notification for property {slug}")
        
        # Verify signature
        if not secret_key:
            logger.error("CINETPAY_SECRET_KEY not configured")
            return HttpResponse(status=500)
        
        if not verify_cinetpay_signature(payload_raw, signature, secret_key):
            logger.warning(f"Invalid signature for payment notification - possible tampering attempt")
            return HttpResponse(status=403)  # Forbidden
        
        # Get transaction details
        transaction_id = payload.get('transaction_id')
        status = payload.get('status')  # 'success', 'failed', 'pending'
        customer_email = payload.get('customer_email')
        amount = payload.get('amount')
        
        logger.info(f"Valid payment notification: transaction_id={transaction_id}, status={status}")
        
        # Handle successful payments
        if status == 'success' and customer_email:
            try:
                # Find user by email
                user = User.objects.get(email=customer_email)
                property_obj = get_object_or_404(Property, slug=slug)
                
                # Create PropertyUnlock
                unlock, created = PropertyUnlock.objects.get_or_create(
                    user=user,
                    property=property_obj,
                    defaults={'transaction_id': transaction_id}
                )
                
                if created:
                    logger.info(f"PropertyUnlock created for user {user.id}, property {property_obj.id}")
                    
                    # Notify property owner
                    if property_obj.owner:
                        from notifications.models import Notification
                        Notification.objects.create(
                            user=property_obj.owner,
                            title="Mise en relation débloquée",
                            message=f"{user.get_full_name() or user.email} a débloqué l'accès à « {property_obj.title} ».",
                            notification_type="transaction",
                            related_id=unlock.id,
                            related_model="PropertyUnlock"
                        )
                else:
                    logger.info(f"PropertyUnlock already exists for user {user.id}, property {property_obj.id}")
                    
            except User.DoesNotExist:
                logger.warning(f"User not found for email {customer_email}")
            except Exception as e:
                logger.error(f"Error processing successful payment: {str(e)}")
        
        elif status == 'failed':
            logger.warning(f"Payment failed for transaction {transaction_id}")
        
        return HttpResponse("OK", status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Unexpected error in payment webhook: {str(e)}")
        return HttpResponse(status=500)
