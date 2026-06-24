from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Q
from django.http import JsonResponse

from properties.models import Property
from agents.models import Agent
from .models import Testimonial
from .forms import ContactForm


def home(request):
    featured = Property.objects.filter(is_published=True, is_validated=True, is_featured=True)[:3]
    for_sale = Property.objects.filter(is_published=True, is_validated=True, transaction_type="vente").exclude(status="brouillon")[:6]
    recently_sold = Property.objects.filter(status__in=["vendu", "loue"], is_published=True, is_validated=True)[:8]
    agents = Agent.objects.filter(is_verified=True).order_by("-rating")[:3]
    testimonials = Testimonial.objects.filter(is_published=True)[:3]

    stats = {
        "sold": Property.objects.filter(status__in=["vendu", "loue"], is_validated=True).count(),
        "clients": Property.objects.filter(requests__isnull=False).values("requests__user").distinct().count(),
        "agents": Agent.objects.filter(is_verified=True).count(),
        "years": 5,
    }

    context = {
        "featured": featured,
        "for_sale": for_sale,
        "recently_sold": recently_sold,
        "agents": agents,
        "testimonials": testimonials,
        "stats": stats,
        "countries": Property.objects.values_list("country", flat=True).distinct(),
        "property_types": Property.PropertyType.choices,
        "category_tiles": [
            ("villa", "Villas", "🏡"),
            ("appartement", "Appartements", "🏢"),
            ("penthouse", "Penthouses", "🌆"),
            ("studio", "Studios", "🛋"),
            ("maison_de_ville", "Maisons de ville", "🏘"),
            ("loft", "Lofts", "🏭"),
        ],
    }
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
        properties = Property.objects.filter(
            Q(title__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q) | Q(address__icontains=q),
            is_published=True, is_validated=True
        )[:6]
        for p in properties:
            results.append({
                "url": p.get_absolute_url(),
                "title": p.title,
                "subtitle": f"{p.city}, {p.country} · {p.price_display}",
                "image": p.primary_image,
            })
        agents = Agent.objects.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(agency_name__icontains=q)
        )[:3]
        for a in agents:
            results.append({
                "url": a.get_absolute_url(),
                "title": a.user.get_full_name(),
                "subtitle": f"Agent · {a.agency_name or 'Indépendant'}",
                "image": a.user.get_avatar_url(),
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
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    result = get_assistant_reply(message, conversation_history=history[-8:])
    matches_data = [
        {"title": p.title, "url": p.get_absolute_url(), "price": p.price_display, "image": p.primary_image}
        for p in result["matches"][:3]
    ]
    return JsonResponse({"reply": result["reply"], "matches": matches_data, "source": result["source"]})
