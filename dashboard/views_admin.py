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
from properties.models import Property
from rental_requests.models import PropertyRequest
from transactions.models import Transaction
from site_settings.models import SiteSettings
from properties.forms import AdminPropertyForm, PropertyImageFormSet
from notifications.models import Notification


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

    # Enhanced statistics
    from favorites.models import Favorite
    from properties.models import PropertyUnlock
    from messaging.models import Message
    
    today = timezone.now().date()
    today_properties = Property.objects.filter(created_at__date=today).count()
    verified_owners = User.objects.filter(role=User.Role.OWNER, verification_status=User.VerificationStatus.APPROVED).count()
    new_owners_this_month = User.objects.filter(role=User.Role.OWNER, date_joined__gte=six_months_ago).count()
    total_views = Property.objects.aggregate(total=Sum('views_count'))['total'] or 0
    total_favorites = Favorite.objects.count()
    total_unlocks = PropertyUnlock.objects.count()
    total_messages = Message.objects.count()

    context = {
        "dash_role": "admin", "active": "overview",
        "clients_count": User.objects.filter(role=User.Role.CLIENT).count(),
        "owners_count": User.objects.filter(role=User.Role.OWNER).count(),
        "verified_owners": verified_owners,
        "new_owners_this_month": new_owners_this_month,
        "properties_count": Property.objects.count(),
        "today_properties": today_properties,
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
        "total_views": total_views,
        "total_favorites": total_favorites,
        "total_unlocks": total_unlocks,
        "total_messages": total_messages,
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
    properties = Property.objects.select_related("owner").order_by("-created_at")
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
    property.validation_status = Property.ValidationStatus.APPROVED
    property.save(update_fields=["is_validated", "is_published", "validation_status"])
    messages.success(request, "Annonce validée et publiée.")
    return redirect("dashboard:admin_properties")


@role_required(User.Role.ADMIN)
def admin_property_reject(request, pk):
    property = get_object_or_404(Property, pk=pk)
    property.is_validated = False
    property.is_published = False
    property.validation_status = Property.ValidationStatus.REJECTED
    property.save(update_fields=["is_validated", "is_published", "validation_status"])
    messages.success(request, "Annonce rejetée.")
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
    transactions = Transaction.objects.select_related("property", "property__owner", "client").order_by("-transaction_date")
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
    from django.db.models import Sum
    from properties.models import PropertyUnlock

    total_revenue = Transaction.objects.aggregate(total=Sum("commission_amount"))["total"] or 0
    recent_unlocks = PropertyUnlock.objects.select_related("user", "property", "property__owner").order_by("-unlocked_at")[:20]

    context = {
        "dash_role": "admin",
        "active": "finances",
        "total_revenue": total_revenue,
        "total_paid_relations": PropertyUnlock.objects.count(),
        "recent_unlocks": recent_unlocks,
    }
    return render(request, "dashboard/admin/finances.html", context)


@role_required(User.Role.ADMIN)
def admin_verifications(request):
    owners = User.objects.filter(role=User.Role.OWNER).exclude(verification_status=User.VerificationStatus.UNVERIFIED).order_by("-verification_date", "-date_joined")
    status = request.GET.get("status")
    if status:
        owners = owners.filter(verification_status=status)
        
    paginator = Paginator(owners, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/verifications.html", {"page_obj": page_obj, "dash_role": "admin", "active": "verifications"})


@role_required(User.Role.ADMIN)
def admin_verification_update(request, pk):
    owner_user = get_object_or_404(User, pk=pk, role=User.Role.OWNER)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "approve":
            owner_user.verification_status = User.VerificationStatus.APPROVED
            owner_user.verification_date = timezone.now()
            owner_user.verification_rejection_reason = ""
            owner_user.save()
            
            try:
                from notifications.models import Notification
                Notification.objects.create(
                    user=owner_user,
                    title="Identité vérifiée",
                    message="Félicitations, votre identité a été vérifiée ! Vous pouvez maintenant publier vos annonces.",
                    notification_type="systeme",
                    link="/dashboard/proprietaire/"
                )
            except Exception:
                pass
                
            messages.success(request, f"Le propriétaire {owner_user.get_full_name()} a été approuvé.")
            
        elif action == "reject":
            reason = request.POST.get("reason")
            owner_user.verification_status = User.VerificationStatus.REJECTED
            owner_user.verification_rejection_reason = reason
            owner_user.save()
            
            try:
                from notifications.models import Notification
                Notification.objects.create(
                    user=owner_user,
                    title="Vérification refusée",
                    message="La vérification de votre identité a été refusée. Veuillez vérifier les motifs et soumettre à nouveau.",
                    notification_type="systeme",
                    link="/dashboard/proprietaire/verification-identite/"
                )
            except Exception:
                pass
                
            messages.warning(request, f"La vérification du propriétaire {owner_user.get_full_name()} a été refusée.")
            
    return redirect("dashboard:admin_verifications")

@role_required(User.Role.ADMIN)
def admin_owners(request):
    owners = User.objects.filter(role=User.Role.OWNER).order_by("-date_joined")
    paginator = Paginator(owners, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/users.html", {"page_obj": page_obj, "dash_role": "admin", "active": "owners", "title_override": "Gestion des propriétaires"})

@role_required(User.Role.ADMIN)
def admin_stats(request):
    return render(request, "dashboard/admin/stats.html", {"dash_role": "admin", "active": "stats"})

@role_required(User.Role.ADMIN)
def admin_reports(request):
    return render(request, "dashboard/admin/reports.html", {"dash_role": "admin", "active": "reports"})


@role_required(User.Role.ADMIN)
def admin_identity_verifications(request):
    """List all identity verification requests."""
    from accounts.models import IdentityVerificationRequest
    
    verifications = IdentityVerificationRequest.objects.select_related("owner", "reviewed_by").order_by("-submitted_at")
    status = request.GET.get("status")
    if status:
        verifications = verifications.filter(status=status)
    
    # Debug: log count
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Total verification requests: {verifications.count()}")
    
    paginator = Paginator(verifications, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    
    context = {
        "dash_role": "admin",
        "active": "identity_verifications",
        "page_obj": page_obj,
        "status_filter": status,
    }
    return render(request, "dashboard/admin/identity_verifications.html", context)


@role_required(User.Role.ADMIN)
def admin_identity_verification_detail(request, pk):
    """View details of a specific identity verification request."""
    from accounts.models import IdentityVerificationRequest
    
    verification = get_object_or_404(IdentityVerificationRequest, pk=pk)
    
    context = {
        "dash_role": "admin",
        "active": "identity_verifications",
        "verification": verification,
        "owner_properties": verification.owner.properties.all(),
    }
    return render(request, "dashboard/admin/identity_verification_detail.html", context)


@role_required(User.Role.ADMIN)
def admin_identity_verification_action(request, pk):
    """Approve, reject, or request resubmission for a verification request."""
    from accounts.models import IdentityVerificationRequest
    
    verification = get_object_or_404(IdentityVerificationRequest, pk=pk)
    
    if request.method == "POST":
        action = request.POST.get("action")
        reason = request.POST.get("reason", "")
        
        if action == "approve":
            verification.approve(request.user)
            messages.success(request, f"La vérification de {verification.owner.get_full_name()} a été approuvée.")
            
            # Send notification to owner
            Notification.objects.create(
                user=verification.owner,
                title="Identité validée avec succès",
                message="Félicitations ! Votre identité a été vérifiée avec succès. Vous pouvez désormais publier vos annonces sur DOMIORA.",
                notification_type="systeme",
                link="/dashboard/proprietaire/verification-identite/"
            )
            
        elif action == "reject":
            if not reason:
                messages.error(request, "Veuillez fournir un motif pour le refus.")
                return redirect("dashboard:admin_identity_verification_detail", pk=pk)
            verification.reject(request.user, reason)
            messages.warning(request, f"La vérification de {verification.owner.get_full_name()} a été refusée.")
            
            # Send notification to owner
            Notification.objects.create(
                user=verification.owner,
                title="Vérification refusée",
                message=f"Vos documents n'ont pas pu être validés. Consultez le motif du refus et soumettez de nouveaux documents. Motif : {reason}",
                notification_type="systeme",
                link="/dashboard/proprietaire/verification-identite/"
            )
            
        elif action == "request_resubmission":
            if not reason:
                messages.error(request, "Veuillez fournir un motif pour la demande de nouvelle soumission.")
                return redirect("dashboard:admin_identity_verification_detail", pk=pk)
            verification.request_resubmission(request.user, reason)
            messages.info(request, f"Une nouvelle soumission a été demandée à {verification.owner.get_full_name()}.")
            
            # Send notification to owner
            Notification.objects.create(
                user=verification.owner,
                title="Nouvelle soumission requise",
                message=f"L'administrateur vous demande de fournir de nouveaux documents afin de finaliser la vérification de votre identité. Motif : {reason}",
                notification_type="systeme",
                link="/dashboard/proprietaire/verification-identite/"
            )
        
        return redirect("dashboard:admin_identity_verifications")
    
    return redirect("dashboard:admin_identity_verification_detail", pk=pk)
