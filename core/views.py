from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from properties.models import Property
from accounts.models import User
from services.rate_limit import is_rate_limited
from .models import Testimonial, BlogPost
from .forms import ContactForm


def _public_contactable_properties():
    from django.db.models import Count
    return Property.objects.filter(
        is_published=True,
        is_validated=True,
        owner__isnull=False,
        owner__role=User.Role.OWNER,
        owner__is_active=True,
    ).annotate(_fav_count=Count('favorited_by', distinct=True))


def home(request):
    public_properties = _public_contactable_properties()
    featured = public_properties.select_related('owner').prefetch_related('images').filter(is_featured=True)[:3]
    for_sale = public_properties.select_related('owner').prefetch_related('images').exclude(status="brouillon")[:8]
    recently_sold = public_properties.select_related('owner').prefetch_related('images').filter(status__in=["vendu", "loue"])[:8]
    testimonials = Testimonial.objects.filter(is_published=True)[:3]

    base_qs = Property.objects.filter(
        is_published=True,
        is_validated=True,
        owner__isnull=False,
        owner__role=User.Role.OWNER,
        owner__is_active=True,
    )
    
    stats_agg = base_qs.aggregate(
        sold=Count('id', filter=Q(status__in=["vendu", "loue"])),
        properties=Count('id')
    )

    stats = {
        "sold": stats_agg["sold"],
        "clients": Property.objects.filter(requests__isnull=False).values("requests__user").distinct().count(),
        "owners": User.objects.filter(role=User.Role.OWNER, verification_status='approved').count(),
        "properties": stats_agg["properties"],
        "years": 5,
    }

    # Category counts
    category_counts = {k: 0 for k, _ in Property.PropertyType.choices}
    counts = base_qs.values("property_type").annotate(count=Count("id"))
    for row in counts:
        category_counts[row["property_type"]] = row["count"]

    context = {
        "featured": featured,
        "for_sale": for_sale,
        "recently_sold": recently_sold,
        "testimonials": testimonials,
        "stats": stats,
        "countries": base_qs.values_list("country", flat=True).distinct(),
        "property_types": Property.PropertyType.choices,
        "category_counts": category_counts,
    }
    # Provide a safe default for templates that expect `favorite_ids`.
    # Templates may render property cards for anonymous users or views
    # that don't include favorites in their context; ensure an empty
    # list is available to avoid VariableDoesNotExist errors.
    context.setdefault("favorite_ids", [])
    return render(request, "core/home.html", context)


def about(request):
    return render(request, "core/about.html")


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_message = form.save()
            try:
                send_mail(
                    subject=f"[DOMIORA] Nouveau message: {contact_message.subject or 'Sans sujet'}",
                    message=f"De: {contact_message.name} <{contact_message.email}>\nTéléphone: {contact_message.phone}\n\n{contact_message.message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, "Votre message a bien été envoyé. Notre équipe vous répondra rapidement.")
            return redirect("core:contact")
    else:
        form = ContactForm()
    return render(request, "core/contact.html", {"form": form})


def search_suggestions(request):
    """Lightweight JSON endpoint powering the navbar command-palette (⌘K) search."""
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        properties = _public_contactable_properties().filter(
            Q(title__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q) | Q(address__icontains=q),
        )[:6]
        for p in properties:
            results.append({
                "url": p.get_absolute_url(),
                "title": p.title,
                "subtitle": f"{p.city}, {p.country} · {p.price_display}",
                "image": p.primary_image,
            })
    return JsonResponse({"results": results})


def assistant_chat(request):
    """POST endpoint for the floating AI assistant widget. Accepts JSON {message, history}."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    import json as _json
    from .ai_assistant import get_assistant_reply

    try:
        payload = _json.loads(request.body or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if payload.get("reset") is True:
        session = getattr(request, "session", None)
        if session is not None:
            session.pop(ASSISTANT_SESSION_KEY, None)
        return JsonResponse({"reply": "", "status": "reset"})
    raw_message = payload.get("message")
    message = raw_message.strip() if isinstance(raw_message, str) else ""
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)
    if len(message) > 4000:
        return JsonResponse({"error": "message is too long"}, status=400)

    history = payload.get("history")
    if not isinstance(history, list):
        history = []

    if is_rate_limited(request, "assistant"):
        return JsonResponse(
            {"error": "Vous avez envoyé beaucoup de messages en peu de temps. Merci de patienter une minute."},
            status=429,
        )

    # L'état de conversation (critères, biens présentés, historique) est conservé côté serveur.
    session = getattr(request, "session", None)
    state = session.get(ASSISTANT_SESSION_KEY) if session is not None else None
    result = get_assistant_reply(message, conversation_history=history[-8:], user=request.user, state=state)
    if session is not None and result.get("state") is not None:
        session[ASSISTANT_SESSION_KEY] = result["state"]

    cards = [_assistant_card(item) for item in result.get("matches", [])[:5]]
    return JsonResponse({
        "reply": result["reply"],
        "matches": cards,
        "cards": cards,
        "actions": result.get("actions", []),
        "comparison": result.get("comparison"),
        "criteria_summary": result.get("criteria_summary", []),
        "quick_replies": result.get("quick_replies", []),
        "intent": result.get("intent"),
        "source": result.get("source"),
    })


ASSISTANT_SESSION_KEY = "assistant_state"


def _assistant_card(item):
    """Carte publique d'un bien (dict du moteur de recherche, ou objet Property pour compatibilité)."""
    if isinstance(item, dict):
        return item
    return {"title": item.title, "url": item.get_absolute_url(), "price": item.price_display, "image": item.primary_image}


def donate(request):
    from properties.fedapay import generate_fedapay_payment_url
    import uuid
    
    if request.method == "GET" and request.GET.get('test_trigger') == '1':
        amount = 2000
        donation_id = str(uuid.uuid4())
        payment_url, transaction_id_or_data = generate_fedapay_payment_url(
            request=request,
            property_slug=f"donation-{donation_id}",
            amount=amount,
            customer_name="Donateur",
            customer_email="",
            customer_phone="",
            is_donation=True
        )
        return HttpResponse(f"DATA: {transaction_id_or_data}")
        
    if request.method == "POST":
        amount = request.POST.get("amount", "2000")
        try:
            amount = int(amount)
            if amount < 100:
                messages.error(request, "Le montant minimum est de 100 FCFA")
                return render(request, "core/donate.html")
        except ValueError:
            messages.error(request, "Montant invalide")
            return render(request, "core/donate.html")
        
        # Générer un ID de transaction unique pour le don
        donation_id = str(uuid.uuid4())
        
        # Générer l'URL de paiement FedaPay
        payment_url, transaction_id_or_data = generate_fedapay_payment_url(
            request=request,
            property_slug=f"donation-{donation_id}",
            amount=amount,
            customer_name="Donateur",
            customer_email=request.POST.get("email", ""),
            customer_phone=request.POST.get("phone", ""),
            is_donation=True
        )
        
        if payment_url:
            return redirect(payment_url)
        else:
            messages.error(request, f"Erreur lors de la génération du lien de paiement. Veuillez réessayer.")
            return render(request, "core/donate.html")
    
    return render(request, "core/donate.html")


def donate_confirmation(request):
    """Page de confirmation après un don"""
    return render(request, "core/donate_confirmation.html")


@csrf_exempt
def donation_notify(request):
    """Webhook FedaPay pour les notifications de don"""
    import logging
    import json
    from properties.fedapay import verify_fedapay_webhook_signature
    
    logger = logging.getLogger(__name__)
    
    if request.method != "POST":
        return HttpResponse(status=405)
    
    try:
        payload_raw = request.body.decode('utf-8')
        signature = request.META.get('HTTP_X_FEDAPAY_SIGNATURE', '')
        
        if not verify_fedapay_webhook_signature(payload_raw, signature):
            logger.warning("Invalid signature for donation notification")
            return HttpResponse(status=403)
        
        payload = json.loads(payload_raw)
        status = payload.get('status')
        amount = payload.get('amount')
        
        logger.info(f"Donation notification: status={status}, amount={amount}")
        
        # Ici vous pouvez ajouter la logique pour enregistrer les dons
        # Créer un modèle Donation si nécessaire
        
        return HttpResponse("OK", status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in donation webhook")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error in donation webhook: {str(e)}")
        return HttpResponse(status=500)


def services(request):
    return render(request, "core/services.html")


def blog(request):
    articles = BlogPost.objects.filter(status='published').select_related('author').order_by('-published_at')
    return render(request, "core/blog.html", {"articles": articles})


def blog_detail(request, slug):
    article = get_object_or_404(BlogPost, slug=slug, status='published')
    article.view_count += 1
    article.save(update_fields=['view_count'])
    articles = BlogPost.objects.filter(status='published').select_related('author').order_by('-published_at')
    return render(request, "core/blog_detail.html", {"article": article, "articles": articles})
