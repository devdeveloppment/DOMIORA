# Importations des bibliothèques mathématiques pour les calculs de distance
from math import radians, sin, cos, sqrt, atan2
from decimal import Decimal
from datetime import timedelta
import uuid
import logging

# Importations Django pour le framework web
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

# Importations des modèles DOMIORA
from favorites.models import Favorite
from rental_requests.forms import PropertyRequestForm
from .fedapay import generate_fedapay_payment_url, verify_fedapay_payment, verify_fedapay_webhook_signature
from .models import Property, PropertyUnlock, PropertyView, SearchAlert

# Configuration du logger pour le suivi des erreurs
logger = logging.getLogger(__name__)

# Récupération du modèle User personnalisé
User = get_user_model()


# Mapping des caractéristiques pour les filtres de recherche.
# Chaque caractéristique principale est associée à plusieurs variantes de libellé,
# afin de rester tolérant vis-à-vis des mots-clés saisis par l'utilisateur.
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


def _public_contactable_properties():
    """Retourne les propriétés publiées, validées et visibles publiquement."""
    # Les biens affichés dans la recherche doivent appartenir à un propriétaire actif
    # et avoir été validés par l'administration avant d'être contactables.
    from django.db.models import Count
    return Property.objects.filter(
        is_published=True,
        is_validated=True,
        owner__isnull=False,
        owner__role=User.Role.OWNER,
        owner__is_active=True,
    ).annotate(_fav_count=Count('favorited_by', distinct=True))


def _property_has_valid_owner(property_obj):
    """Vérifie si la propriété a un propriétaire en règle et actif."""
    return bool(
        property_obj.owner
        and property_obj.owner.role == User.Role.OWNER
        and property_obj.owner.is_active
    )


def _haversine_km(lat1, lon1, lat2, lon2):
    """Calcule la distance en kilomètres entre deux coordonnées GPS selon la formule de Haversine."""
    r = 6371.0  # Rayon moyen de la Terre en kilomètres.
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _default_nearby_services(property_obj):
    """Fournit une liste de services de proximité par défaut pour une propriété."""
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
    """Ajoute les filtres liés aux équipements sélectionnés sur un queryset de propriétés."""
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
    """Construit un libellé lisible pour une alerte de recherche à partir des critères saisis."""
    city = (request_data.get("city") or "").strip()
    property_type = (request_data.get("type") or "").strip()
    price_max = (request_data.get("price_max") or "").strip()
    property_label = dict(Property.PropertyType.choices).get(property_type, "")

    # Le nom de l'alerte se base d'abord sur la ville et le type de bien, si présents.
    if property_label and city:
        base_name = f"{property_label} à {city}"
    elif property_label:
        base_name = property_label
    elif city:
        base_name = city
    else:
        base_name = "Recherche sauvegardée"

    # Ajoute le budget maximum lorsque l'utilisateur le précise dans le formulaire.
    if price_max:
        try:
            formatted_budget = f"{int(float(price_max)):,}".replace(",", " ")
            return f"{base_name} / budget {formatted_budget}"
        except ValueError:
            return base_name
    return base_name


@login_required
def save_search_alert(request):
    """Sauvegarde une alerte de recherche pour l'utilisateur connecté."""
    if request.method != "POST":
        return redirect("properties:list")

    # Si aucun nom n'est fourni, on construit automatiquement un libellé explicite.
    name = (request.POST.get("name") or "").strip() or _build_alert_name(request.POST)

    # Création complète de l'alerte avec les critères choisis par l'utilisateur.
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
    """Affiche et gère les alertes de recherche enregistrées par l'utilisateur."""
    if request.method == "POST":
        action = request.POST.get("action")
        alert_id = request.POST.get("alert_id")
        alert = get_object_or_404(SearchAlert, pk=alert_id, user=request.user)

        # Activation/désactivation ou suppression de l'alerte choisie.
        if action == "toggle":
            alert.is_active = not alert.is_active
            alert.save()
            messages.success(request, f"Alerte {'activée' if alert.is_active else 'désactivée'} : {alert.name}")
        elif action == "delete":
            alert.delete()
            messages.success(request, "Alerte supprimée.")
        return redirect("properties:my_alerts")

    # On récupère toutes les alertes de l'utilisateur, les plus récentes en premier.
    alerts = SearchAlert.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "properties/my_alerts.html", {"alerts": alerts})


def property_list(request):
    """Vue principale de la liste des propriétés avec filtres et recherche avancée."""
    # Requête optimisée pour afficher les biens publiés sans charger inutilement les relations lourdes.
    qs = (
        Property.objects.filter(
            is_published=True,
            is_validated=True,
            owner__isnull=False,
            owner__role=User.Role.OWNER,
            owner__is_active=True,
        )
        .select_related("owner")
        .prefetch_related("images")
    )

    # Filtre par type de transaction (vente/location)
    transaction = request.GET.get("transaction")
    if transaction in ("vente", "location"):
        qs = qs.filter(transaction_type=transaction)

    # Filtre par type de propriété
    property_type = request.GET.get("type")
    if property_type:
        qs = qs.filter(property_type=property_type)

    # Filtre par pays
    country = request.GET.get("country")
    if country:
        qs = qs.filter(country=country)

    # Filtre par ville (recherche insensible à la casse)
    city = request.GET.get("city")
    if city:
        qs = qs.filter(city__icontains=city)

    # Filtre par prix minimum
    price_min = request.GET.get("price_min")
    if price_min:
        qs = qs.filter(price__gte=price_min)

    # Filtre par prix maximum
    price_max = request.GET.get("price_max")
    if price_max:
        qs = qs.filter(price__lte=price_max)

    # Filtre par nombre de chambres minimum
    bedrooms = request.GET.get("bedrooms")
    if bedrooms:
        qs = qs.filter(bedrooms__gte=bedrooms)

    # Filtre par nombre de salles de bain minimum
    bathrooms = request.GET.get("bathrooms")
    if bathrooms:
        qs = qs.filter(bathrooms__gte=bathrooms)

    # Filtre par surface minimum
    surface_min = request.GET.get("surface_min")
    if surface_min:
        qs = qs.filter(surface_area__gte=surface_min)

    # Filtre par statut (vendu/loué ou disponible)
    status = request.GET.get("status")
    if status == "vendu_loue":
        qs = qs.filter(status__in=["vendu", "loue"])
    elif status == "disponible":
        qs = qs.filter(status="disponible")

    # Filtre par propriétaire vérifié
    if request.GET.get("owner_verified") == "1":
        qs = qs.filter(owner__verification_status=User.VerificationStatus.APPROVED)

    # Filtre par propriété validée
    if request.GET.get("property_verified") == "1":
        qs = qs.filter(is_validated=True)

    # Application des filtres de caractéristiques
    selected_features = request.GET.getlist("feature")
    if selected_features:
        qs = _apply_feature_filters(qs, selected_features)

    # Recherche textuelle sur titre, ville, adresse et quartier
    q = request.GET.get("q")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(city__icontains=q) | Q(address__icontains=q) | Q(neighborhood__icontains=q))

    # Recherche géographique par coordonnées GPS et rayon
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    radius_km = request.GET.get("radius_km", 15)
    if lat and lng:
        try:
            lat = float(lat)
            lng = float(lng)
            radius_km = float(radius_km)
            nearby = []
            # Calcule la distance pour chaque propriété avec coordonnées
            for item in qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True):
                distance = _haversine_km(lat, lng, float(item.latitude), float(item.longitude))
                if distance <= radius_km:
                    item.distance_km = round(distance, 1)
                    nearby.append(item)
            nearby.sort(key=lambda item: getattr(item, "distance_km", 9999))
            qs = nearby
        except (TypeError, ValueError):
            pass

    # Tri des résultats
    sort = request.GET.get("sort", "recent")
    if isinstance(qs, list):
        # Tri en Python pour les résultats géographiques
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
        # Tri en base de données pour les résultats standards
        sort_map = {
            "recent": "-created_at",
            "price_asc": "price",
            "price_desc": "-price",
            "popular": "-views_count",
        }
        qs = qs.order_by(sort_map.get(sort, "-created_at"))
        paginator = Paginator(qs, 12)

    # Pagination des résultats
    page_obj = paginator.get_page(request.GET.get("page"))

    # Récupération des favoris de l'utilisateur connecté
    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(Favorite.objects.filter(user=request.user).values_list("property_id", flat=True))

    # Récupération des alertes de recherche sauvegardées
    saved_alerts = []
    if request.user.is_authenticated:
        saved_alerts = SearchAlert.objects.filter(user=request.user).order_by("-created_at")[:5]

    # Récupération des pays disponibles pour les filtres
    countries = Property.objects.filter(
        is_published=True, 
        is_validated=True, 
        owner__isnull=False, 
        owner__role=User.Role.OWNER, 
        owner__is_active=True
    ).values_list("country", flat=True).distinct()

    # Contexte du template avec toutes les données nécessaires
    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
        "property_types": Property.PropertyType.choices,
        "countries": countries,
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
    # Optimized property retrieval with minimal queries
    property_obj = get_object_or_404(
        Property.objects.filter(
            is_published=True,
            is_validated=True,
            owner__isnull=False,
            owner__role=User.Role.OWNER,
            owner__is_active=True,
        ).select_related("owner").prefetch_related("images", "amenities"),
        slug=slug,
    )

    # Optimize view count update - use atomic increment and skip Python increment
    Property.objects.filter(pk=property_obj.pk).update(views_count=F("views_count") + 1)
    # Note: We don't increment property_obj.views_count in Python to avoid stale data

    # Optimize session handling - only create if needed
    if not request.session.session_key:
        request.session.save()

    # Optimize PropertyView creation - make it optional/lazy
    # Only create if user is authenticated or it's a new session
    should_track_view = True
    if request.user.is_authenticated:
        # Check if user viewed this property recently (within last hour)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_view = PropertyView.objects.filter(
            user=request.user,
            property=property_obj,
            viewed_at__gte=one_hour_ago
        ).exists()
        should_track_view = not recent_view
    else:
        # For anonymous users, check by session
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_view = PropertyView.objects.filter(
            session_key=request.session.session_key,
            property=property_obj,
            viewed_at__gte=one_hour_ago
        ).exists()
        should_track_view = not recent_view

    if should_track_view:
        PropertyView.objects.create(
            user=request.user if request.user.is_authenticated else None,
            property=property_obj,
            ip_address=request.META.get("REMOTE_ADDR"),
            session_key=request.session.session_key,
        )

    # Optimize favorite and unlock checks with single queries
    is_favorite = False
    has_unlocked = False
    if request.user.is_authenticated:
        # Single query for favorite check
        is_favorite = Favorite.objects.filter(user=request.user, property=property_obj).exists()
        
        # Single query for unlock check with owner optimization
        if property_obj.owner:
            has_unlocked = PropertyUnlock.objects.filter(
                user=request.user, 
                property__owner=property_obj.owner
            ).exists()
        else:
            has_unlocked = PropertyUnlock.objects.filter(
                user=request.user, 
                property=property_obj
            ).exists()
        
        # Owners and admins always have access
        if request.user.role != User.Role.CLIENT:
            has_unlocked = True

    # Optimize similar properties query - simplified logic
    # Use only city and property_type for faster query
    similar_qs = (
        Property.objects.filter(
            is_published=True,
            is_validated=True,
            owner__isnull=False,
            owner__role=User.Role.OWNER,
            owner__is_active=True,
        )
        .filter(city=property_obj.city)
        .exclude(pk=property_obj.pk)
        .select_related("owner")
        .prefetch_related("images", "amenities")[:12]
    )

    # If not enough by city, add by property type
    similar_list = list(similar_qs)
    if len(similar_list) < 6:
        additional_qs = (
            Property.objects.filter(
                is_published=True,
                is_validated=True,
                owner__isnull=False,
                owner__role=User.Role.OWNER,
                owner__is_active=True,
                property_type=property_obj.property_type,
            )
            .exclude(pk__in=[p.pk for p in similar_list] + [property_obj.pk])
            .select_related("owner")
            .prefetch_related("images", "amenities")[:6]
        )
        similar_list.extend(list(additional_qs))

    # Simple similarity score - optimized
    def similarity_score(item):
        score = 0
        if item.city == property_obj.city:
            score += 3
        if item.property_type == property_obj.property_type:
            score += 2
        if abs(float(item.price) - float(property_obj.price)) / float(property_obj.price or 1) < 0.25:
            score += 1
        return score

    similar = sorted(similar_list, key=similarity_score, reverse=True)[:6]

    # Use cached nearby services or default
    nearby_services = property_obj.nearby_services or _default_nearby_services(property_obj)
    share_url = request.build_absolute_uri(property_obj.get_absolute_url())
    share_text = f"{property_obj.title} - {property_obj.price_display}"

    if request.method == "POST":
        messages.info(request, "Veuillez régler les frais de mise en relation avant de contacter le propriétaire.")
        return redirect("properties:payment_redirect", slug=property_obj.slug)

    request_form = None
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
        _public_contactable_properties()
        .filter(pk__in=ids)
        .select_related("owner")
        .prefetch_related("amenities", "images")
    )
    properties.sort(key=lambda item: ids.index(str(item.pk)))
    for item in properties:
        item.amenity_names = set(item.amenities.values_list("name", flat=True))

    all_amenities = sorted({name for item in properties for name in item.amenity_names})
    return render(request, "properties/compare.html", {"properties": properties, "all_amenities": all_amenities})


def property_payment_redirect(request, slug):
    property_obj = get_object_or_404(_public_contactable_properties(), slug=slug)

    # Permettre aux admins/proprios de tester le flux (commenté la restriction)
    # if request.user.is_authenticated and request.user.role != User.Role.CLIENT:
    #     messages.error(request, "Seul un compte client peut effectuer une mise en relation.")
    #     return redirect("properties:detail", slug=slug)

    if request.user.is_authenticated:
        # Per-owner unlock: check if user already paid for ANY property of this owner
        owner = property_obj.owner
        if owner and PropertyUnlock.objects.filter(user=request.user, property__owner=owner).exists():
            messages.info(request, "Vous êtes déjà en relation avec ce propriétaire.")
            return redirect("properties:detail", slug=slug)

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

        payment_url, trans_id = generate_fedapay_payment_url(
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
        
        if payment_url:
            return redirect(payment_url)
        
        logger.error("Payment URL generation failed - showing error to user")
        messages.error(request, "Erreur d'initialisation du paiement. Veuillez réessayer ou contacter le support.")
        return redirect("properties:detail", slug=slug)

    from .fedapay import _get_fedapay_public_key, _get_fedapay_base_url
    return render(request, "properties/payment_init.html", {
        "property": property_obj,
        "fedapay_public_key": _get_fedapay_public_key(),
        "fedapay_sandbox": getattr(settings, 'FEDAPAY_SANDBOX', True),
    })


def property_payment_confirmation(request, slug):
    property_obj = get_object_or_404(_public_contactable_properties().select_related("owner"), slug=slug)

    # FedaPay envoie dans le callback : ?id=<id>&status=approved&token=<token>
    # On lit les GET params en priorité, puis la session comme fallback
    fedapay_id = (
        request.GET.get("id")
        or request.GET.get("transaction_id")
        or request.session.get("fedapay_transaction_id")
    )
    fedapay_status = request.GET.get("status", "")

    logger.info(f"Confirmation paiement: slug={slug}, fedapay_id={fedapay_id}, status_get={fedapay_status}")

    if fedapay_id:
        # Si FedaPay envoie status=approved dans le GET, on accepte directement,
        # sinon on vérifie via l'API
        if fedapay_status == "approved":
            is_paid = True
            logger.info("FedaPay: statut 'approved' reçu directement dans le callback GET.")
        else:
            is_paid, _ = verify_fedapay_payment(fedapay_id)

        if is_paid:
            if not request.user.is_authenticated:
                pending = request.session.get("pending_payment", {})
                email = pending.get("email")
                name = pending.get("name", "Client")
                phone = pending.get("phone", "")
                password = pending.get("password", "")

                if email:
                    import random
                    import string

                    username = f"guest_{name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
                    while User.objects.filter(username=username).exists():
                        username = f"guest_{name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"

                    if not password:
                        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

                    user = User.objects.filter(email=email, role=User.Role.CLIENT).first()
                    if user:
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

                    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                    request.session["dash_role"] = "client"
                    request.session.modified = True

            if request.user.is_authenticated:
                # Nettoyer la session de paiement
                for _k in ("fedapay_transaction_id", "pending_transaction_id", "pending_payment"):
                    request.session.pop(_k, None)
                request.session["dash_role"] = "client"
                request.session.modified = True

                owner = property_obj.owner
                PropertyUnlock.objects.get_or_create(user=request.user, property=property_obj)
                messages.success(request, "Paiement confirm\u00e9 ! Votre espace client est pr\u00eat. Vous pouvez maintenant contacter le propri\u00e9taire depuis vos mises en relation.")

                if owner:
                    from notifications.models import Notification
                    from messaging.models import Conversation, Message

                    conversation, created = Conversation.objects.get_or_create(
                        buyer=request.user,
                        owner=owner,
                        property=property_obj
                    )

                    if created:
                        Message.objects.create(
                            conversation=conversation,
                            sender=request.user,
                            body=f"Bonjour, je suis int\u00e9ress\u00e9 par votre bien \u00ab {property_obj.title} \u00bb. J'aimerais avoir plus d'informations.",
                            message_type=Message.MessageType.TEXT
                        )

                    Notification.objects.create(
                        user=owner,
                        title="Mise en relation d\u00e9bloqu\u00e9e",
                        message=f"{request.user.get_full_name() or request.user.username} a pay\u00e9 les frais de mise en relation pour \u00ab {property_obj.title} \u00bb.",
                        notification_type="systeme",
                        link=f"/dashboard/proprietaire/messagerie/{conversation.pk}/",
                    )

                return redirect("dashboard:client_unlocked")

    logger.warning(f"Confirmation paiement \u00e9chou\u00e9e: fedapay_id={fedapay_id}, GET={dict(request.GET)}")
    messages.error(request, "Le paiement n'a pas pu \u00eatre valid\u00e9.")
    return redirect("properties:detail", slug=slug)



@csrf_exempt
def property_payment_notify(request, slug):
    """
    FedaPay webhook pour les notifications de paiement.
    Vérifie la signature et met à jour le statut PropertyUnlock.
    """
    import logging
    import json
    
    logger = logging.getLogger(__name__)
    
    # Only accept POST requests
    if request.method != "POST":
        return HttpResponse(status=405)
    
    try:
        # Récupération du corps et de la signature FedaPay
        payload_raw = request.body.decode('utf-8')
        signature = request.META.get('HTTP_X_FEDAPAY_SIGNATURE', '')
        
        # Parse JSON
        payload = json.loads(payload_raw)
        logger.info(f"Notification de paiement FedaPay reçue pour le bien {slug}")
        
        if not verify_fedapay_webhook_signature(payload_raw, signature):
            logger.warning("Signature FedaPay invalide — possible tentative de falsification")
            return HttpResponse(status=403)
        
        # Données de la transaction FedaPay
        event = payload.get('name', '')  # ex: 'transaction.approved'
        transaction_data = payload.get('data', {}).get('transaction', {})
        transaction_id = transaction_data.get('id')
        status = transaction_data.get('status', '')  # 'approved', 'declined', 'canceled'
        customer_email = (transaction_data.get('customer') or {}).get('email', '')
        amount = transaction_data.get('amount')
        
        logger.info(f"Notification FedaPay valide: event={event}, id={transaction_id}, statut={status}")
        
        # Handle successful payments
        if status == 'approved' and customer_email:
            try:
                # Find user by email
                user = User.objects.get(email=customer_email, role=User.Role.CLIENT)
                property_obj = get_object_or_404(_public_contactable_properties(), slug=slug)
                
                # Create PropertyUnlock
                unlock, created = PropertyUnlock.objects.get_or_create(
                    user=user,
                    property=property_obj,
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
