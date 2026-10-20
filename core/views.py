from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Q
from django.http import Http404, JsonResponse, HttpResponse
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
        "search_tabs": [("tous", "Tout"), ("vente", "À vendre"), ("location", "À louer"), ("terrain", "Terrain"), ("commercial", "Commercial")],
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


DONATION_SUGGESTIONS = (300, 500, 700, 1000, 2000, 5000)


def donate(request):
    """Don volontaire, montant libre (suggestions indicatives)."""
    from . import donations

    context = {"suggestions": DONATION_SUGGESTIONS, "min_amount": donations.min_amount(),
               "simulation": settings.PAYMENT_MODE == "simulation", "form": {}}
    if request.method == "POST":
        context["form"] = {k: request.POST.get(k, "") for k in ("amount", "email", "phone")}
        if is_rate_limited(request, "donation", limit=10, window=3600):
            messages.error(request, "Trop de tentatives. Réessayez dans un moment.")
            return render(request, "core/donate.html", context, status=429)
        try:
            amount = donations.parse_amount(request.POST.get("amount"))
            _, url = donations.start_donation(request, amount, request.POST.get("email", "").strip(),
                                              request.POST.get("phone", "").strip())
        except donations.DonationError as error:
            messages.error(request, str(error))
            return render(request, "core/donate.html", context)
        return redirect(url)
    return render(request, "core/donate.html", context)


def donation_simulator(request, reference):
    """Démonstration : l'utilisateur choisit l'issue du paiement ; aucun argent réel."""
    from .models import Donation

    donation = get_object_or_404(Donation, reference=reference, provider=Donation.Provider.SIMULATION)
    if settings.PAYMENT_MODE != "simulation":
        raise Http404
    if request.method == "POST" and not donation.is_terminal:
        outcome = request.POST.get("outcome", "")
        if outcome in ("approved", "declined", "canceled"):
            Donation.objects.filter(pk=donation.pk).update(simulated_outcome=outcome)
        return redirect("core:donation_return", reference=donation.reference)
    return render(request, "core/donation_simulator.html", {"donation": donation})


def donation_return(request, reference):
    """Retour du prestataire : le statut est relu côté serveur, jamais lu dans l'URL."""
    from . import donations
    from .models import Donation

    donation = get_object_or_404(Donation, reference=reference)
    donation = donations.verify(donation, source="return")
    return render(request, "core/donate_confirmation.html", {"donation": donation})


def donate_confirmation(request):
    """Ancienne URL de confirmation : sans référence, aucun don ne peut être confirmé."""
    return redirect("core:donate")


@csrf_exempt
def donation_notify(request):
    """Ancienne adresse de notification des dons : même traitement que le webhook FedaPay commun."""
    from payments.views import fedapay_webhook

    return fedapay_webhook(request)


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


# ─────────────────────────────────────────────────────────────────────────────
# PWA : manifeste, service worker (portée racine) et page hors connexion
# ─────────────────────────────────────────────────────────────────────────────
def pwa_manifest(request):
    from django.templatetags.static import static

    data = {
        "name": "DOMIORA — Immobilier de confiance",
        "short_name": "DOMIORA",
        "lang": "fr",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "background_color": "#faf7f5",
        "theme_color": "#5a1a24",
        "icons": [
            {"src": static("pwa/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("pwa/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


def service_worker(request):
    from django.contrib.staticfiles import finders

    path = finders.find("pwa/sw.js")
    with open(path, encoding="utf-8") as fh:
        response = HttpResponse(fh.read(), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "core/offline.html")


def favicon(request):
    """/favicon.ico (demandé d'office par les navigateurs) → icône du site, URL calculée à la requête."""
    from django.contrib.staticfiles.storage import staticfiles_storage

    return redirect(staticfiles_storage.url("pwa/icon-192.png"), permanent=True)
