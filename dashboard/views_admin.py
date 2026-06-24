import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta

from .decorators import role_required
from accounts.models import User
from agents.models import Agent
from properties.models import Property
from rental_requests.models import PropertyRequest
from transactions.models import Transaction
from site_settings.models import SiteSettings
from properties.forms import AdminPropertyForm, PropertyImageFormSet


@role_required(User.Role.ADMIN)
def admin_overview(request):
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly = (
        Transaction.objects.filter(transaction_date__gte=six_months_ago)
        .annotate(month=TruncMonth("transaction_date"))
        .values("month")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("month")
    )
    chart_labels = [m["month"].strftime("%b %Y") for m in monthly]
    chart_values = [float(m["total"] or 0) for m in monthly]

    # Unified activity feed (Stripe/Notion-style recent activity stream)
    activity = []
    for u in User.objects.order_by("-date_joined")[:6]:
        activity.append({"icon": "👤", "text": f"{u.get_full_name() or u.username} a créé un compte ({u.get_role_display()})", "time": u.date_joined})
    for p in Property.objects.order_by("-created_at")[:6]:
        activity.append({"icon": "🏠", "text": f"Nouveau bien publié : « {p.title} »", "time": p.created_at})
    for r in PropertyRequest.objects.order_by("-created_at")[:6]:
        activity.append({"icon": "📨", "text": f"{r.user.get_full_name() or r.user.username} a fait une demande pour « {r.property.title} »", "time": r.created_at})
    for t in Transaction.objects.order_by("-created_at")[:6]:
        activity.append({"icon": "💰", "text": f"Transaction enregistrée : « {t.property.title} » — ${t.amount:,.0f}".replace(",", " "), "time": t.created_at})
    activity.sort(key=lambda a: a["time"], reverse=True)
    activity = activity[:10]

    # Property distribution
    prop_distribution = list(Property.objects.values("property_type").annotate(count=Count("id")).order_by("-count")[:5])
    for p in prop_distribution:
        p["label"] = str(p["property_type"]).replace("_", " ").title()

    context = {
        "dash_role": "admin", "active": "overview",
        "users_count": User.objects.filter(role=User.Role.BUYER).count(),
        "agents_count": Agent.objects.count(),
        "properties_count": Property.objects.count(),
        "published_properties_count": Property.objects.filter(is_published=True, is_validated=True).count(),
        "transactions_count": Transaction.objects.count(),
        "pending_requests_count": PropertyRequest.objects.filter(status="en_attente").count(),
        "for_rent_count": Property.objects.filter(transaction_type="location").count(),
        "for_sale_count": Property.objects.filter(transaction_type="vente").count(),
        "sold_count": Property.objects.filter(status="vendu").count(),
        "rented_count": Property.objects.filter(status="loue").count(),
        "pending_validation_count": Property.objects.filter(is_validated=False).count(),
        "total_revenue": Transaction.objects.aggregate(total=Sum("amount"))["total"] or 0,
        "total_commission": Transaction.objects.aggregate(total=Sum("commission_amount"))["total"] or 0,
        "recent_transactions": Transaction.objects.select_related("property", "client").order_by("-transaction_date")[:5],
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "chart_labels": json.dumps(chart_labels),
        "chart_values": json.dumps(chart_values),
        "prop_distribution": prop_distribution,
        "activity": activity,
    }
    return render(request, "dashboard/admin/overview.html", context)


@role_required(User.Role.ADMIN)
def admin_users(request):
    users = User.objects.all().order_by("-date_joined")
    role = request.GET.get("role")
    if role:
        users = users.filter(role=role)
    q = request.GET.get("q")
    if q:
        users = users.filter(username__icontains=q)
    paginator = Paginator(users, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/users.html", {"page_obj": page_obj, "dash_role": "admin", "active": "users"})


@role_required(User.Role.ADMIN)
def admin_user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_suspended = not user.is_suspended
    user.is_active = not user.is_suspended
    user.save(update_fields=["is_suspended", "is_active"])
    messages.success(request, f"Compte {'suspendu' if user.is_suspended else 'réactivé'}.")
    return redirect("dashboard:admin_users")


@role_required(User.Role.ADMIN)
def admin_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        user.delete()
        messages.success(request, "Utilisateur supprimé.")
    return redirect("dashboard:admin_users")


@role_required(User.Role.ADMIN)
def admin_properties(request):
    properties = Property.objects.select_related("agent__user").order_by("-created_at")
    status = request.GET.get("status")
    if status:
        properties = properties.filter(status=status)
    paginator = Paginator(properties, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/properties.html", {"page_obj": page_obj, "dash_role": "admin", "active": "properties"})


@role_required(User.Role.ADMIN)
def admin_property_create(request):
    if request.method == "POST":
        form = AdminPropertyForm(request.POST)
        formset = PropertyImageFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            property_obj = form.save()
            formset.instance = property_obj
            formset.save()
            messages.success(request, "Propriété créée avec succès.")
            return redirect("dashboard:admin_properties")
    else:
        form = AdminPropertyForm()
        formset = PropertyImageFormSet()
    
    context = {"form": form, "formset": formset, "dash_role": "admin", "active": "properties", "action": "Ajouter"}
    return render(request, "dashboard/admin/property_form.html", context)


@role_required(User.Role.ADMIN)
def admin_property_edit(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)
    if request.method == "POST":
        form = AdminPropertyForm(request.POST, instance=property_obj)
        formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Propriété modifiée avec succès.")
            return redirect("dashboard:admin_properties")
    else:
        form = AdminPropertyForm(instance=property_obj)
        formset = PropertyImageFormSet(instance=property_obj)
    
    context = {"form": form, "formset": formset, "dash_role": "admin", "active": "properties", "action": "Modifier"}
    return render(request, "dashboard/admin/property_form.html", context)


@role_required(User.Role.ADMIN)
def admin_property_validate(request, pk):
    property = get_object_or_404(Property, pk=pk)
    property.is_validated = True
    property.is_published = True
    property.save(update_fields=["is_validated", "is_published"])
    messages.success(request, "Annonce validée et publiée.")
    return redirect("dashboard:admin_properties")


@role_required(User.Role.ADMIN)
def admin_property_delete(request, pk):
    property = get_object_or_404(Property, pk=pk)
    if request.method == "POST":
        property.delete()
        messages.success(request, "Bien supprimé.")
    return redirect("dashboard:admin_properties")


@role_required(User.Role.ADMIN)
def admin_transactions(request):
    transactions = Transaction.objects.select_related("property", "agent__user", "client").order_by("-transaction_date")
    status = request.GET.get("status")
    if status:
        transactions = transactions.filter(status=status)
    paginator = Paginator(transactions, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/transactions.html", {"page_obj": page_obj, "dash_role": "admin", "active": "transactions"})


@role_required(User.Role.ADMIN)
def admin_settings(request):
    settings_obj = SiteSettings.load()
    if request.method == "POST":
        for field in [
            "site_name", "tagline", "contact_email", "contact_phone", "address",
            "opening_hours_weekdays", "opening_hours_weekend",
            "facebook", "instagram", "linkedin", "twitter", "youtube", "tiktok", "whatsapp",
            "smtp_host", "smtp_port", "smtp_user",
        ]:
            value = request.POST.get(field)
            if value is not None:
                setattr(settings_obj, field, value)
        settings_obj.smtp_use_tls = bool(request.POST.get("smtp_use_tls"))
        if request.FILES.get("logo"):
            settings_obj.logo = request.FILES["logo"]
        settings_obj.save()
        messages.success(request, "Paramètres mis à jour.")
        return redirect("dashboard:admin_settings")
    return render(request, "dashboard/admin/settings.html", {"settings": settings_obj, "dash_role": "admin", "active": "settings"})


@role_required(User.Role.ADMIN)
def admin_finances(request):
    from subscriptions.models import PaymentHistory, AgentSubscription
    from django.db.models import Sum

    # Récupérer l'historique des paiements d'abonnement
    payments = PaymentHistory.objects.all().select_related('subscription__agent__user', 'subscription__plan').order_by('-payment_date')
    
    # Calculer les revenus totaux (Abonnements)
    total_subscription_revenue = PaymentHistory.objects.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0

    # Abonnements actifs vs expirés
    active_subscriptions = AgentSubscription.objects.filter(status='active').count()
    expired_subscriptions = AgentSubscription.objects.filter(status='expired').count()

    context = {
        "dash_role": "admin",
        "active": "finances",
        "payments": payments[:50],  # 50 derniers paiements
        "total_revenue": total_subscription_revenue,
        "active_subs_count": active_subscriptions,
        "expired_subs_count": expired_subscriptions,
    }
    return render(request, "dashboard/admin/finances.html", context)
