import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
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

# Tableau de bord administratif principal.
# Cette vue centralise les statistiques, les activités récentes et la synthèse
# de l'état global du site pour l'administrateur.


@role_required(User.Role.ADMIN)
def admin_overview(request):
    """Vue d'accueil de l'administration : statistiques globales et activité récente."""
    six_months_ago = timezone.now() - timedelta(days=180)
    
    # Only use real transactions for statistics - no demo data
    monthly = (
        Transaction.objects.filter(transaction_date__gte=six_months_ago)
        .annotate(month=TruncMonth("transaction_date"))
        .values("month")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("month")
    )
    
    # Handle case with no real transactions
    if not monthly:
        # Create empty chart data for last 6 months
        chart_labels = []
        chart_values = []
        for i in range(6):
            month = timezone.now() - timedelta(days=30*i)
            chart_labels.append(month.strftime("%b %Y"))
            chart_values.append(0)
        chart_labels.reverse()
        chart_values.reverse()
    else:
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
    # Only include real transactions in activity feed
    for t in Transaction.objects.order_by("-created_at")[:6]:
        activity.append({"icon": "💰", "text": f"Transaction enregistrée : « {t.property.title} » — ${t.amount:,.0f}".replace(",", " "), "time": t.created_at})
    activity.sort(key=lambda a: a["time"], reverse=True)
    activity = activity[:10]

    # Property distribution
    prop_distribution = list(Property.objects.values("property_type").annotate(count=Count("id")).order_by("-count")[:5])
    for p in prop_distribution:
        p["label"] = str(p["property_type"]).replace("_", " ").title()

    # Enhanced statistics — all aggregated into minimal DB round-trips
    from favorites.models import Favorite
    from properties.models import PropertyUnlock
    from messaging.models import Message

    today = timezone.now().date()

    # Single aggregate for all Property counts
    prop_agg = Property.objects.aggregate(
        total=Count('id'),
        published=Count('id', filter=Q(is_published=True, is_validated=True)),
        pending_validation=Count('id', filter=Q(is_validated=False)),
        for_rent=Count('id', filter=Q(transaction_type='location')),
        for_sale=Count('id', filter=Q(transaction_type='vente')),
        sold=Count('id', filter=Q(status='vendu')),
        rented=Count('id', filter=Q(status='loue')),
        today_new=Count('id', filter=Q(created_at__date=today)),
        total_views=Sum('views_count'),
    )

    # Single aggregate for all User counts
    user_agg = User.objects.aggregate(
        clients=Count('id', filter=Q(role=User.Role.CLIENT)),
        owners=Count('id', filter=Q(role=User.Role.OWNER)),
        verified_owners=Count('id', filter=Q(role=User.Role.OWNER, verification_status=User.VerificationStatus.APPROVED)),
        new_owners=Count('id', filter=Q(role=User.Role.OWNER, date_joined__gte=six_months_ago)),
    )

    # Single aggregate for all Transaction amounts (only real transactions)
    txn_agg = Transaction.objects.aggregate(
        total_count=Count('id'),
        total_revenue=Sum('amount'),
        total_commission=Sum('commission_amount'),
    )
    
    # Log info about real vs demo data
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Real transactions count: {txn_agg['total_count']}")
    logger.info(f"Real total revenue: {txn_agg['total_revenue']}")

    total_favorites = Favorite.objects.count()
    total_unlocks = PropertyUnlock.objects.count()
    total_messages = Message.objects.count()
    pending_requests_count = PropertyRequest.objects.filter(status='en_attente').count()

    context = {
        "dash_role": "admin", "active": "overview",
        "clients_count": user_agg['clients'],
        "owners_count": user_agg['owners'],
        "verified_owners": user_agg['verified_owners'],
        "new_owners_this_month": user_agg['new_owners'],
        "properties_count": prop_agg['total'],
        "today_properties": prop_agg['today_new'],
        "published_properties_count": prop_agg['published'],
        "transactions_count": txn_agg['total_count'],
        "pending_requests_count": pending_requests_count,
        "for_rent_count": prop_agg['for_rent'],
        "for_sale_count": prop_agg['for_sale'],
        "sold_count": prop_agg['sold'],
        "rented_count": prop_agg['rented'],
        "pending_validation_count": prop_agg['pending_validation'],
        "total_revenue": txn_agg['total_revenue'] or 0,
        "total_commission": txn_agg['total_commission'] or 0,
        "total_views": prop_agg['total_views'] or 0,
        "total_favorites": total_favorites,
        "total_unlocks": total_unlocks,
        "total_messages": total_messages,
        "recent_transactions": Transaction.objects.select_related("property", "client").order_by("-transaction_date")[:5] if Transaction.objects.exists() else [],
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "chart_labels": json.dumps(chart_labels),
        "chart_values": json.dumps(chart_values),
        "prop_distribution": prop_distribution,
        "activity": activity,
    }
    return render(request, "dashboard/admin/overview.html", context)


@role_required(User.Role.ADMIN)
def admin_users(request):
    """Liste les utilisateurs du système avec filtres et pagination."""
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
    """Crée une propriété depuis l'espace d'administration."""
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
    """Modifie une propriété existante depuis l'administration."""
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
    """Valide une annonce et la publie immédiatement."""
    property = get_object_or_404(Property, pk=pk)
    property.is_validated = True
    property.is_published = True
    property.validation_status = Property.ValidationStatus.APPROVED
    property.save(update_fields=["is_validated", "is_published", "validation_status"])

    # La validation ne dépend jamais de la vidéo : la génération est mise en file (Celery)
    # et n'est relancée que si aucune vidéo n'est prête ou en cours.
    from properties.video.service import has_ready_video, in_progress, request_virtual_tour

    if has_ready_video(property):
        messages.success(request, "Annonce validée et publiée. La visite virtuelle est déjà disponible.")
    elif in_progress(property):
        messages.success(request, "Annonce validée et publiée. La visite virtuelle est en cours de génération.")
    else:
        queued, video_message = request_virtual_tour(property)
        messages.success(request, "Annonce validée et publiée.")
        (messages.info if queued else messages.warning)(request, video_message)

    return redirect("dashboard:admin_properties")


@role_required(User.Role.ADMIN)
def admin_property_video_generate(request, pk):
    """L'administrateur peut (re)lancer la visite virtuelle de n'importe quel bien (sans le publier)."""
    if request.method != "POST":
        return redirect("dashboard:admin_properties")
    from properties.video.service import request_virtual_tour

    property = get_object_or_404(Property, pk=pk)
    queued, video_message = request_virtual_tour(property)
    (messages.success if queued else messages.warning)(request, video_message)
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
    """Affiche les transactions réelles enregistrées dans le système."""
    transactions = Transaction.objects.select_related("property", "property__owner", "client").order_by("-transaction_date")
    status = request.GET.get("status")
    if status:
        transactions = transactions.filter(status=status)
    paginator = Paginator(transactions, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/transactions.html", {"page_obj": page_obj, "dash_role": "admin", "active": "transactions"})


@role_required(User.Role.ADMIN)
def admin_settings(request):
    """Gère les paramètres globaux du site et les coordonnées de contact."""
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
    """Affiche les éléments financiers du système : revenus et paiements."""
    from django.db.models import Sum
    from properties.models import PropertyUnlock

    # Only real transactions contribute to revenue
    total_revenue = Transaction.objects.aggregate(total=Sum("commission_amount"))["total"] or 0
    recent_unlocks = PropertyUnlock.objects.select_related("user", "property", "property__owner").order_by("-unlocked_at")[:20]

    # Log real revenue info
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Real revenue from transactions: {total_revenue}")
    logger.info(f"Total paid relations: {PropertyUnlock.objects.count()}")

    context = {
        "dash_role": "admin",
        "active": "finances",
        "total_revenue": total_revenue,
        "total_paid_relations": PropertyUnlock.objects.count(),
        "recent_unlocks": recent_unlocks,
        "note": "Statistiques basées uniquement sur les transactions réelles (pas de données de test)"
    }
    return render(request, "dashboard/admin/finances.html", context)


@role_required(User.Role.ADMIN)
def admin_verifications(request):
    """Liste les propriétaires dont la vérification d'identité est en cours ou terminée."""
    owners = User.objects.filter(role=User.Role.OWNER).exclude(verification_status=User.VerificationStatus.UNVERIFIED).order_by("-verification_date", "-date_joined")
    status = request.GET.get("status")
    if status:
        owners = owners.filter(verification_status=status)
        
    paginator = Paginator(owners, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/verifications.html", {"page_obj": page_obj, "dash_role": "admin", "active": "verifications"})


@role_required(User.Role.ADMIN)
def admin_verification_update(request, pk):
    """Approuve ou refuse la vérification d'un propriétaire."""
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
    """Liste les propriétaires enregistrés sur la plateforme."""
    owners = User.objects.filter(role=User.Role.OWNER).order_by("-date_joined")
    paginator = Paginator(owners, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/admin/users.html", {"page_obj": page_obj, "dash_role": "admin", "active": "owners", "title_override": "Gestion des propriétaires"})

@role_required(User.Role.ADMIN)
def admin_stats(request):
    """Page des statistiques avancées de l'administration."""
    return render(request, "dashboard/admin/stats.html", {"dash_role": "admin", "active": "stats"})

@role_required(User.Role.ADMIN)
def admin_reports(request):
    """Page des rapports et analyses de l'administration."""
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
    """Approve, reject, request resubmission, schedule visit, or complete visit for a verification request."""
    from accounts.models import IdentityVerificationRequest
    from datetime import datetime
    
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
        
        elif action == "schedule_visit":
            visit_date_str = request.POST.get("visit_date")
            agent_name = request.POST.get("agent_name")
            
            if not visit_date_str or not agent_name:
                messages.error(request, "Veuillez fournir la date de visite et le nom de l'agent.")
                return redirect("dashboard:admin_identity_verification_detail", pk=pk)
            
            try:
                visit_date = datetime.fromisoformat(visit_date_str)
                verification.schedule_field_visit(request.user, visit_date, agent_name)
                messages.success(request, f"Une visite sur le terrain a été programmée pour {verification.owner.get_full_name()}.")
                
                # Send notification to owner
                Notification.objects.create(
                    user=verification.owner,
                    title="Visite sur le terrain programmée",
                    message=f"Une visite de vérification sur le terrain a été programmée le {visit_date.strftime('%d/%m/%Y à %H:%M')}. Un agent DOMIORA vous contactera pour confirmer le rendez-vous.",
                    notification_type="systeme",
                    link="/dashboard/proprietaire/verification-identite/"
                )
            except ValueError:
                messages.error(request, "Format de date invalide.")
                return redirect("dashboard:admin_identity_verification_detail", pk=pk)
        
        elif action == "complete_visit":
            visit_notes = request.POST.get("visit_notes", "")
            property_verified = request.POST.get("property_verified") == "on"
            property_notes = request.POST.get("property_notes", "")
            
            if not visit_notes:
                messages.error(request, "Veuillez fournir des notes pour la visite.")
                return redirect("dashboard:admin_identity_verification_detail", pk=pk)
            
            verification.complete_field_visit(request.user, visit_notes, property_verified, property_notes)
            messages.success(request, f"La visite sur le terrain pour {verification.owner.get_full_name()} a été enregistrée comme effectuée.")
            
            # Send notification to owner
            Notification.objects.create(
                user=verification.owner,
                title="Visite sur le terrain effectuée",
                message="La visite de vérification sur le terrain a été effectuée. Votre dossier est en cours de validation finale par notre équipe.",
                notification_type="systeme",
                link="/dashboard/proprietaire/verification-identite/"
            )
        
        return redirect("dashboard:admin_identity_verifications")
    
    return redirect("dashboard:admin_identity_verification_detail", pk=pk)
