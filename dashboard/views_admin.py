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
    """Vue d'accueil de l'administration : indicateurs calculés depuis la base (voir dashboard.metrics)."""
    from appointments.models import Appointment
    from . import metrics

    period, period_label, start = metrics.resolve_period(request.GET.get("periode"))
    finance = metrics.finance_summary(start)
    counts = metrics.platform_counts(start)
    revenue = metrics.monthly_revenue(6)
    signups = metrics.monthly_counts(User.objects.all(), "date_joined", 6)
    listings = metrics.monthly_counts(Property.objects.all(), "created_at", 6)

    # Flux d'activité récente (relations chargées en une requête par source).
    activity = []
    for u in User.objects.order_by("-date_joined")[:6]:
        activity.append({"icon": "user", "text": f"{u.get_full_name() or u.username} a créé un compte ({u.get_role_display()})", "time": u.date_joined})
    for p in Property.objects.order_by("-created_at")[:6]:
        activity.append({"icon": "home", "text": f"Nouvelle annonce : « {p.title} »", "time": p.created_at})
    for r in PropertyRequest.objects.select_related("user", "property").order_by("-created_at")[:6]:
        activity.append({"icon": "inbox", "text": f"{r.user.get_full_name() or r.user.username} a fait une demande pour « {r.property.title} »", "time": r.created_at})
    for pay in metrics.contact_fee_payments().select_related("client").order_by("-paid_at")[:6]:
        tag = " (test)" if pay.is_test else ""
        activity.append({"icon": "pay", "text": f"Mise en relation payée{tag} : {pay.amount} {pay.currency} par {pay.client.get_full_name() or pay.client.username}", "time": pay.paid_at})
    activity.sort(key=lambda a: a["time"], reverse=True)

    prop_distribution = list(Property.objects.values("property_type").annotate(count=Count("id")).order_by("-count")[:5])
    for p in prop_distribution:
        p["label"] = str(p["property_type"]).replace("_", " ").title()

    context = {
        "dash_role": "admin", "active": "overview",
        "period": period, "period_label": period_label, "periods": metrics.PERIODS,
        "finance": finance,
        "counts": counts,
        "pending_appointments": Appointment.objects.filter(status="en_attente").count(),
        "recent_payments": metrics.contact_fee_payments().select_related("client", "owner", "property").order_by("-paid_at")[:6],
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "chart": {"labels": revenue["labels"], "real": revenue["real"], "test": revenue["test"],
                  "signups": signups, "listings": listings},
        "prop_distribution": prop_distribution,
        "activity": activity[:10],
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
    properties = Property.objects.select_related("owner").prefetch_related("images").order_by("-created_at")
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
    """Valide une annonce et la publie immédiatement (propriétaire vérifié uniquement)."""
    if request.method != "POST":
        return redirect("dashboard:admin_properties")
    property = get_object_or_404(Property.objects.select_related("owner"), pk=pk)
    # Règle métier : seule l'annonce d'un propriétaire vérifié peut être publiée.
    if not (property.owner and property.owner.is_verified_owner):
        messages.error(request, "Le propriétaire de cette annonce n'est pas vérifié : publication impossible.")
        return redirect("dashboard:admin_properties")
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
    if request.method != "POST":
        return redirect("dashboard:admin_properties")
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
    """Finances : revenus réels et de test séparés, par source et par période."""
    from . import metrics

    period, period_label, start = metrics.resolve_period(request.GET.get("periode"))
    payments = metrics.contact_fee_payments().select_related("client", "owner", "property").order_by("-paid_at")
    if start:
        payments = payments.filter(paid_at__gte=start)
    subs = metrics.subscription_payments().select_related("owner", "plan").order_by("-paid_at")
    if start:
        subs = subs.filter(paid_at__gte=start)
    context = {
        "dash_role": "admin", "active": "finances",
        "period": period, "period_label": period_label, "periods": metrics.PERIODS,
        "finance": metrics.finance_summary(start),
        "chart": metrics.monthly_revenue(12),
        "payments": payments[:25],
        "subscription_payments": subs[:25],
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
    """Statistiques : entonnoir de conversion, annonces les plus vues, répartition par ville."""
    from favorites.models import Favorite
    from messaging.models import ListingInquiry
    from properties.models import PropertyUnlock, PropertyView
    from . import metrics

    period, period_label, start = metrics.resolve_period(request.GET.get("periode"))

    def since(qs, field):
        return qs.filter(**{f"{field}__gte": start}) if start else qs

    views = since(PropertyView.objects.all(), "viewed_at")
    inquiries = since(ListingInquiry.objects.all(), "created_at")
    inquiry_agg = inquiries.aggregate(total=Count("id"), answered=Count("id", filter=Q(status="answered")))
    funnel = [
        ("Vues d'annonces", views.count()),
        ("Ajouts en favoris", since(Favorite.objects.all(), "created_at").count()),
        ("Questions avant relation", inquiry_agg["total"]),
        ("Mises en relation", since(PropertyUnlock.objects.all(), "unlocked_at").count()),
    ]
    top = max((n for _, n in funnel), default=0)
    funnel = [{"label": label, "count": n, "pct": round(100 * n / top) if top else 0} for label, n in funnel]

    top_ids = list(views.values("property_id").annotate(n=Count("id")).order_by("-n")[:10])
    props = Property.objects.select_related("owner").in_bulk([row["property_id"] for row in top_ids])
    top_properties = [{"property": props[row["property_id"]], "views": row["n"]} for row in top_ids if row["property_id"] in props]

    by_city = list(
        Property.objects.filter(is_published=True, is_validated=True)
        .values("city").annotate(count=Count("id")).order_by("-count")[:8]
    )
    city_max = max((c["count"] for c in by_city), default=0)
    for c in by_city:
        c["pct"] = round(100 * c["count"] / city_max) if city_max else 0

    return render(request, "dashboard/admin/stats.html", {
        "dash_role": "admin", "active": "stats",
        "period": period, "period_label": period_label, "periods": metrics.PERIODS,
        "funnel": funnel, "top_properties": top_properties, "by_city": by_city,
        "inquiries": inquiry_agg,
        "answer_rate": round(100 * inquiry_agg["answered"] / inquiry_agg["total"]) if inquiry_agg["total"] else None,
        "chart": {
            "labels": metrics.month_labels(12),
            "clients": metrics.monthly_counts(User.objects.filter(role=User.Role.CLIENT), "date_joined", 12),
            "owners": metrics.monthly_counts(User.objects.filter(role=User.Role.OWNER), "date_joined", 12),
        },
    })


REPORTS = {
    "paiements": "Mises en relation payées",
    "abonnements": "Paiements d'abonnement",
    "dons": "Dons reçus",
    "utilisateurs": "Utilisateurs inscrits",
    "annonces": "Annonces",
}


@role_required(User.Role.ADMIN)
def admin_reports(request):
    """Rapports : exports CSV par période (ouverture directe dans Excel)."""
    from . import metrics

    period, period_label, start = metrics.resolve_period(request.GET.get("periode"))
    return render(request, "dashboard/admin/reports.html", {
        "dash_role": "admin", "active": "reports",
        "period": period, "period_label": period_label, "periods": metrics.PERIODS,
        "reports": REPORTS, "finance": metrics.finance_summary(start),
    })


@role_required(User.Role.ADMIN)
def admin_report_export(request, kind):
    """Export CSV (séparateur « ; », UTF-8 avec BOM) d'un rapport sur la période demandée."""
    import csv
    from django.http import Http404, HttpResponse
    from . import metrics

    if kind not in REPORTS:
        raise Http404
    period, _, start = metrics.resolve_period(request.GET.get("periode"))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="domiora-{kind}-{period}-{timezone.localdate():%Y%m%d}.csv"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    fmt = lambda dt: timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else ""

    if kind == "paiements":
        qs = metrics.contact_fee_payments().select_related("client", "owner", "property").order_by("-paid_at")
        if start:
            qs = qs.filter(paid_at__gte=start)
        writer.writerow(["Date", "Référence", "Client", "Propriétaire", "Annonce", "Montant", "Devise", "Moyen", "Nature"])
        for p in qs.iterator():
            writer.writerow([fmt(p.paid_at), p.reference, p.client.username, p.owner.username,
                             p.property.title if p.property else "", p.amount, p.currency,
                             p.get_provider_display(), "Test" if p.is_test else "Réel"])
    elif kind == "abonnements":
        qs = metrics.subscription_payments().select_related("owner", "plan").order_by("-paid_at")
        if start:
            qs = qs.filter(paid_at__gte=start)
        writer.writerow(["Date", "Référence", "Propriétaire", "Formule", "Motif", "Montant", "Devise", "Nature"])
        for p in qs.iterator():
            writer.writerow([fmt(p.paid_at), p.reference, p.owner.username, p.plan.name, p.get_purpose_display(),
                             p.amount, p.currency, "Test" if p.is_simulated else "Réel"])
    elif kind == "dons":
        from django.db.models.functions import Coalesce

        from core.models import Donation

        qs = Donation.objects.filter(status=Donation.Status.APPROVED).annotate(
            paid_at=Coalesce("confirmed_at", "updated_at")).order_by("-paid_at")
        if start:
            qs = qs.filter(paid_at__gte=start)
        writer.writerow(["Date", "Référence", "Montant", "Devise", "Moyen", "Nature"])
        for d in qs.iterator():
            writer.writerow([fmt(d.paid_at), d.reference, d.amount, d.currency, d.get_provider_display(),
                             "Test" if d.is_test else "Réel"])
    elif kind == "utilisateurs":
        qs = User.objects.order_by("-date_joined")
        if start:
            qs = qs.filter(date_joined__gte=start)
        # Pas d'e-mail ni de téléphone : l'export ne contient aucune coordonnée personnelle.
        writer.writerow(["Inscription", "Identifiant", "Nom", "Rôle", "Vérification", "Actif"])
        for u in qs.iterator():
            writer.writerow([fmt(u.date_joined), u.username, u.get_full_name(), u.get_role_display(),
                             u.get_verification_status_display(), "Oui" if u.is_active else "Non"])
    else:
        qs = Property.objects.select_related("owner").order_by("-created_at")
        if start:
            qs = qs.filter(created_at__gte=start)
        writer.writerow(["Création", "Titre", "Type", "Transaction", "Ville", "Prix", "Propriétaire", "Publiée", "Validée", "Vues"])
        for p in qs.iterator():
            writer.writerow([fmt(p.created_at), p.title, p.get_property_type_display(), p.get_transaction_type_display(),
                             p.city, p.price, p.owner.username if p.owner else "", "Oui" if p.is_published else "Non",
                             "Oui" if p.is_validated else "Non", p.views_count])
    return response


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
