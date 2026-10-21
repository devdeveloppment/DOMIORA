from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.db.models.functions import TruncMonth
from datetime import timedelta
import json

from .decorators import role_required
from accounts.models import User
from properties.models import Property, PropertyImage
from properties.forms import MAX_IMAGES_PER_UPLOAD, PropertyForm, validate_property_images
from properties.video.service import has_ready_video, in_progress, request_virtual_tour, status_payload
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from rental_requests.models import PropertyRequest
from notifications.models import Notification
from accounts.forms import ProfileForm


@role_required(User.Role.OWNER)
def owner_overview(request):
    """Vue d'accueil du propriétaire : synthèse de ses biens et statistiques."""
    properties = Property.objects.filter(owner=request.user).select_related("owner").prefetch_related("images")
    # Removed visit requests from owner dashboard as per user requirement
    # Owners should only see paid connections through messaging, not visit requests
    from favorites.models import Favorite
    from messaging.models import Message
    from properties.models import PropertyUnlock, PropertyView

    six_months_ago = timezone.now() - timedelta(days=180)
    
    # Enhanced statistics
    total_views = properties.aggregate(total=Sum('views_count'))['total'] or 0
    total_favorites = Favorite.objects.filter(property__owner=request.user).count()
    total_messages = Message.objects.filter(conversation__owner=request.user).count()
    total_unlocks = PropertyUnlock.objects.filter(property__owner=request.user).count()
    paid_contacts = total_unlocks
    
    # Property status breakdown
    property_stats = properties.aggregate(
        total=Count('id'),
        validated_count=Count('id', filter=Q(is_validated=True)),
        pending_validation_count=Count('id', filter=Q(validation_status='pending')),
        rejected_count=Count('id', filter=Q(validation_status='rejected')),
        available_count=Count('id', filter=Q(status='disponible')),
        sold_count=Count('id', filter=Q(status='vendu')),
        rented_count=Count('id', filter=Q(status='loue')),
        published_count=Count('id', filter=Q(is_published=True)),
    )
    
    validated_count = property_stats['validated_count']
    pending_validation_count = property_stats['pending_validation_count']
    rejected_count = property_stats['rejected_count']
    available_count = property_stats['available_count']
    sold_count = property_stats['sold_count']
    rented_count = property_stats['rented_count']
    published_count = property_stats['published_count']

    from . import metrics

    chart = {
        "labels": metrics.month_labels(6),
        "views": metrics.monthly_counts(PropertyView.objects.filter(property__owner=request.user), "viewed_at", 6),
        "favorites": metrics.monthly_counts(Favorite.objects.filter(property__owner=request.user), "created_at", 6),
        "relations": metrics.monthly_counts(PropertyUnlock.objects.filter(property__owner=request.user), "unlocked_at", 6),
    }
    context = {
        "dash_role": "owner",
        "active": "overview",
        "properties_count": property_stats['total'],
        "published_count": published_count,
        "validated_count": validated_count,
        "pending_validation_count": pending_validation_count,
        "rejected_count": rejected_count,
        "total_views": total_views,
        "total_favorites": total_favorites,
        "total_messages": total_messages,
        "total_unlocks": total_unlocks,
        "paid_contacts": paid_contacts,
        "validated_count": validated_count,
        "rejected_count": rejected_count,
        "available_count": available_count,
        "sold_count": sold_count,
        "rented_count": rented_count,
        "recent_properties": properties.order_by("-created_at")[:5],
        "chart": chart,
    }
    return render(request, "dashboard/owner/overview.html", context)


@role_required(User.Role.OWNER)
def owner_properties(request):
    """Affiche les biens du propriétaire avec pagination."""
    properties = Property.objects.filter(owner=request.user).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/properties.html", {"page_obj": page_obj, "dash_role": "owner", "active": "properties"})


def _save_new_images(property, files):
    """Ajoute les photos à la suite des existantes ; la première photo d'un bien sans photo devient principale."""
    start = property.images.count()
    for i, f in enumerate(files):
        PropertyImage.objects.create(property=property, image=f, is_primary=(start == 0 and i == 0), order=start + i)


def _property_form_context(form, property=None):
    return {
        "form": form,
        "is_edit": property is not None,
        "property": property,
        "max_images": MAX_IMAGES_PER_UPLOAD,
        "dash_role": "owner",
        "active": "properties",
    }


@role_required(User.Role.OWNER)
def owner_property_create(request):
    """Permet à un propriétaire d'ajouter une nouvelle annonce immobilière."""
    if request.user.verification_status != User.VerificationStatus.APPROVED:
        messages.error(request, f"Votre identité doit être vérifiée pour publier un bien. Statut actuel : {request.user.get_verification_status_display()}")
        return redirect("dashboard:owner_verify_identity")

    if request.method == "POST":
        form = PropertyForm(request.POST, request.FILES)
        files = request.FILES.getlist("images")
        image_errors = validate_property_images(files)
        if form.is_valid() and not image_errors:
            with transaction.atomic():
                property = form.save(commit=False)
                property.owner = request.user
                # Force la propriété à être en attente de validation et non publiée
                property.is_published = False
                property.is_validated = False
                property.is_featured = False
                property.validation_status = Property.ValidationStatus.PENDING
                property.save()
                form.save_m2m()
                _save_new_images(property, files)

            messages.success(request, "Le bien a été ajouté avec succès et est en attente de validation par l'administrateur.")
            # Visite virtuelle : génération asynchrone (ne publie ni ne valide le bien).
            queued, video_message = request_virtual_tour(property)
            (messages.info if queued else messages.warning)(request, video_message)
            return redirect("dashboard:owner_properties")
        context = _property_form_context(form)
        context["image_errors"] = image_errors
        context["files_lost"] = bool(files) or bool(request.FILES.get("uploaded_tour_video"))
        return render(request, "dashboard/owner/property_form.html", context, status=400)

    return render(request, "dashboard/owner/property_form.html", _property_form_context(PropertyForm()))


@role_required(User.Role.OWNER)
def owner_property_edit(request, pk):
    """Modifie un bien déjà enregistré par le propriétaire (les photos existantes sont conservées)."""
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        form = PropertyForm(request.POST, request.FILES, instance=property)
        files = request.FILES.getlist("images")
        image_errors = validate_property_images(files)
        if form.is_valid() and not image_errors:
            with transaction.atomic():
                updated_property = form.save(commit=False)
                # Si la propriété n'est pas encore validée, la remettre en attente de validation
                if not updated_property.is_validated:
                    updated_property.is_published = False
                    updated_property.validation_status = Property.ValidationStatus.PENDING
                updated_property.save()
                form.save_m2m()
                _save_new_images(updated_property, files)

            messages.success(request, "Les modifications du bien ont été enregistrées.")
            if files:
                # De nouvelles photos : la visite virtuelle doit les inclure.
                queued, video_message = request_virtual_tour(updated_property)
                (messages.info if queued else messages.warning)(request, video_message)
            return redirect("dashboard:owner_properties")
        property.refresh_from_db()  # l'en-tête et les photos affichent l'état enregistré, pas la saisie refusée
        context = _property_form_context(form, property)
        context["image_errors"] = image_errors
        context["files_lost"] = bool(files) or bool(request.FILES.get("uploaded_tour_video"))
        return render(request, "dashboard/owner/property_form.html", context, status=400)

    return render(request, "dashboard/owner/property_form.html", _property_form_context(PropertyForm(instance=property), property))


@role_required(User.Role.OWNER)
def owner_property_delete(request, pk):
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        property.delete()
        messages.success(request, "Le bien a été supprimé.")
    return redirect("dashboard:owner_properties")


@role_required(User.Role.OWNER)
@require_POST
def owner_property_toggle_publish(request, pk):
    """Publie ou retire une annonce du site public (seule une annonce validée peut être en ligne)."""
    property = get_object_or_404(Property, pk=pk, owner=request.user)

    if request.user.verification_status != User.VerificationStatus.APPROVED:
        messages.error(request, "Votre identité doit être vérifiée pour publier/dépublier un bien.")
        return redirect("dashboard:owner_properties")
    if not property.is_published and not property.is_validated:
        messages.error(request, "Cette annonce doit d'abord être validée par l'administration avant d'être mise en ligne.")
        return redirect("dashboard:owner_properties")

    property.is_published = not property.is_published
    property.save(update_fields=["is_published"])
    messages.success(request, "L'annonce est en ligne." if property.is_published else "L'annonce est retirée du site.")
    return redirect("dashboard:owner_properties")


@role_required(User.Role.OWNER)
@require_POST
def owner_property_image_delete(request, pk, image_id):
    """Supprime une image d'un bien du propriétaire."""
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    deleted, _ = PropertyImage.objects.filter(pk=image_id, property=property).delete()
    if deleted:
        _refresh_virtual_tour_after_photo_change(request, property)
    return redirect("dashboard:owner_property_edit", pk=property.pk)


# ---------------------------------------------------------------------------
# Visite virtuelle (propriétaire, uniquement sur SES biens)
# ---------------------------------------------------------------------------
def _refresh_virtual_tour_after_photo_change(request, property):
    """
    Après suppression / réordonnancement d'une photo, une vidéo existante (ou en cours)
    ne correspond plus aux photos : elle est masquée et régénérée.
    Le délai regroupe plusieurs modifications rapides en une seule génération.
    """
    if has_ready_video(property) or in_progress(property) or property.virtual_tour_video:
        queued, video_message = request_virtual_tour(property, countdown=10)
        (messages.info if queued else messages.warning)(request, video_message)


@role_required(User.Role.OWNER)
@require_POST
def owner_property_image_move(request, pk, image_id):
    """Déplace une photo d'un cran (ordre utilisé par la galerie et la visite virtuelle)."""
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    images = list(property.images.order_by("order", "id"))
    index = next((i for i, image in enumerate(images) if image.pk == image_id), None)
    if index is None:
        return redirect("dashboard:owner_property_edit", pk=property.pk)
    target = index - 1 if request.POST.get("direction") == "up" else index + 1
    if 0 <= target < len(images):
        images[index], images[target] = images[target], images[index]
        for position, image in enumerate(images):
            if image.order != position:
                # update() : évite la reconversion WebP de PropertyImage.save()
                PropertyImage.objects.filter(pk=image.pk).update(order=position)
        _refresh_virtual_tour_after_photo_change(request, property)
    return redirect("dashboard:owner_property_edit", pk=property.pk)


@role_required(User.Role.OWNER)
@require_POST
def owner_property_video_generate(request, pk):
    """Demande la (re)génération de la visite virtuelle d'un bien du propriétaire connecté."""
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    queued, video_message = request_virtual_tour(property)
    (messages.success if queued else messages.warning)(request, video_message)
    return redirect("dashboard:owner_property_edit", pk=property.pk)


@role_required(User.Role.OWNER)
@require_GET
def owner_property_video_status(request, pk):
    """État et progression de la visite virtuelle (JSON), pour le propriétaire du bien uniquement."""
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    return JsonResponse(status_payload(property))


# REMOVED: owner_requests and owner_request_update_status functions
# Visit requests should not be displayed on owner dashboard per user requirement
# Owners only see paid connections through messaging system


@role_required(User.Role.OWNER)
def owner_verify_identity(request):
    """Soumet et suit la vérification d'identité du propriétaire."""
    import logging

    from accounts.models import IdentityVerificationRequest

    logger = logging.getLogger(__name__)
    latest_request = request.user.verification_requests.first()

    if request.method == "POST":
        locked_statuses = {
            User.VerificationStatus.APPROVED,
            User.VerificationStatus.PENDING_FIELD_VISIT,
            User.VerificationStatus.FIELD_VISIT_COMPLETED,
        }
        if request.user.verification_status in locked_statuses:
            messages.info(request, "Votre vérification est déjà validée ou en cours de vérification terrain : aucun nouvel envoi n'est nécessaire.")
            return redirect("dashboard:owner_verify_identity")
        if request.user.verification_requests.filter(status=IdentityVerificationRequest.Status.PENDING).exists():
            messages.info(request, "Vos documents sont déjà en cours d'analyse. Vous serez notifié dès qu'un administrateur les aura examinés.")
            return redirect("dashboard:owner_verify_identity")

        id_document_front = request.FILES.get("id_document_front")
        id_document_back = request.FILES.get("id_document_back")
        id_document_type = (request.POST.get("id_document_type") or "").strip()[:50]
        id_document_number = (request.POST.get("id_document_number") or "").strip()[:50]

        if not id_document_front or not id_document_back:
            messages.error(request, "Veuillez fournir les deux faces de votre pièce d'identité.")
            return redirect("dashboard:owner_verify_identity")
        file_errors = validate_property_images([id_document_front, id_document_back])
        if file_errors:
            for error in file_errors:
                messages.error(request, error)
            return redirect("dashboard:owner_verify_identity")

        try:
            with transaction.atomic():
                verification_request = IdentityVerificationRequest.objects.create(
                    owner=request.user,
                    id_document_front=id_document_front,
                    id_document_back=id_document_back,
                    id_document_type=id_document_type,
                    id_document_number=id_document_number,
                    status=IdentityVerificationRequest.Status.PENDING,
                )
                request.user.verification_status = User.VerificationStatus.PENDING_DOCUMENTS
                request.user.save(update_fields=["verification_status"])

                Notification.objects.create(
                    user=request.user,
                    title="Demande de vérification soumise",
                    message="Vos documents ont été envoyés avec succès. Ils seront examinés par un administrateur. Vous recevrez une notification dès que votre identité sera validée.",
                    notification_type="systeme",
                    link="/dashboard/proprietaire/verification-identite/",
                )
                for admin in User.objects.filter(role=User.Role.ADMIN):
                    Notification.objects.create(
                        user=admin,
                        title="Nouvelle demande de vérification d'identité",
                        message=f"Le propriétaire {request.user.get_full_name() or request.user.username} vient de soumettre ses documents d'identité. Veuillez examiner les pièces et valider ou refuser la demande.",
                        notification_type="systeme",
                        link="/dashboard/admin-panel/verifications-identite/",
                    )
            # Journal sans donnée personnelle : ni numéro de pièce, ni nom de fichier.
            logger.info("Demande de vérification #%s soumise (propriétaire %s)", verification_request.pk, request.user.pk)
            messages.success(request, "Vos documents ont été envoyés avec succès. Ils seront examinés par un administrateur. Vous recevrez une notification dès que votre identité sera validée.")
        except Exception as exc:
            logger.error("Échec de la soumission de vérification (propriétaire %s) : %s", request.user.pk, exc.__class__.__name__)
            messages.error(request, "L'envoi de vos documents a échoué. Réessayez dans quelques instants.")
        return redirect("dashboard:owner_verify_identity")

    context = {
        "dash_role": "owner",
        "active": "verification",
        "latest_request": latest_request,
    }
    return render(request, "dashboard/owner/verify_identity.html", context)


@role_required(User.Role.OWNER)
def owner_profile(request):
    """Permet à un propriétaire de modifier son profil."""
    if request.method == "POST":
        user_form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("dashboard:owner_profile")
    else:
        user_form = ProfileForm(instance=request.user)
    return render(request, "dashboard/owner/profile.html", {"form": user_form, "dash_role": "owner", "active": "profile"})


@role_required(User.Role.OWNER)
def owner_notifications(request):
    """Affiche les notifications destinées au propriétaire uniquement."""
    # Only show notifications intended for the OWNER role:
    # - notifications with a link pointing to /dashboard/proprietaire/
    # - notifications with no link (generic system notifications)
    # Exclude client-specific and admin-specific notifications.
    from django.db.models import Q
    notifications = Notification.objects.filter(user=request.user).filter(
        Q(link__startswith='/dashboard/proprietaire/') | Q(link='')
    ).exclude(link__startswith='/dashboard/admin-panel/')
    context = {
        "dash_role": "owner",
        "active": "notifications",
        "notifications": notifications,
    }
    request.session["dash_role"] = "owner"
    return render(request, "notifications/list.html", context)

@role_required(User.Role.OWNER)
def owner_pending_properties(request):
    """Liste les biens encore en attente de validation."""
    properties = Property.objects.filter(owner=request.user, is_published=False).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/properties.html", {"page_obj": page_obj, "dash_role": "owner", "active": "pending_properties", "title_override": "Annonces en attente"})

@role_required(User.Role.OWNER)
def owner_published_properties(request):
    """Liste les biens déjà publiés et visibles pour les clients."""
    properties = Property.objects.filter(owner=request.user, is_published=True).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/properties.html", {"page_obj": page_obj, "dash_role": "owner", "active": "published_properties", "title_override": "Annonces validées"})

@role_required(User.Role.OWNER)
def owner_stats(request):
    """Performance par annonce sur la période : vues, favoris, mises en relation, conversations."""
    from favorites.models import Favorite
    from messaging.models import Conversation
    from properties.models import PropertyUnlock, PropertyView
    from . import metrics

    period, period_label, start = metrics.resolve_period(request.GET.get("periode"))

    def per_property(qs, date_field):
        if start:
            qs = qs.filter(**{f"{date_field}__gte": start})
        return dict(qs.values_list("property_id").annotate(n=Count("id")))

    mine = {"property__owner": request.user}
    views = per_property(PropertyView.objects.filter(**mine), "viewed_at")
    favorites = per_property(Favorite.objects.filter(**mine), "created_at")
    relations = per_property(PropertyUnlock.objects.filter(**mine), "unlocked_at")
    conversations = per_property(Conversation.objects.filter(owner=request.user), "created_at")

    rows = []
    for prop in Property.objects.filter(owner=request.user).order_by("-created_at"):
        v = views.get(prop.pk, 0)
        r = relations.get(prop.pk, 0)
        rows.append({
            "property": prop, "views": v, "favorites": favorites.get(prop.pk, 0), "relations": r,
            "conversations": conversations.get(prop.pk, 0),
            "conversion": round(100 * r / v, 1) if v else None,
        })
    totals = {k: sum(row[k] for row in rows) for k in ("views", "favorites", "relations", "conversations")}
    return render(request, "dashboard/owner/stats.html", {
        "dash_role": "owner", "active": "stats",
        "period": period, "period_label": period_label, "periods": metrics.PERIODS,
        "rows": rows, "totals": totals,
    })

@role_required(User.Role.OWNER)
def owner_settings(request):
    return render(request, "dashboard/owner/settings.html", {"dash_role": "owner", "active": "settings"})


@role_required(User.Role.OWNER)
def owner_messaging(request):
    """Accède au centre de messagerie du propriétaire."""
    from messaging.models import Conversation
    
    # Ensure session has correct dash_role
    request.session["dash_role"] = "owner"
    
    # Get most recent conversation and redirect to it directly
    conversation = (
        Conversation.objects
        .filter(owner=request.user)
        .select_related("buyer", "property")
        .order_by("-updated_at")
        .first()
    )
    
    if conversation:
        # Redirect directly to the most recent conversation
        return redirect("dashboard:owner_conversation_detail", pk=conversation.pk)
    
    # If no conversations, show empty inbox
    context = {
        "conversations": Conversation.objects.none(),
        "active": "messaging",
        "dash_role": "owner",
    }
    return render(request, "messaging/inbox.html", context)


@role_required(User.Role.OWNER)
def owner_conversation_detail(request, pk):
    """Owner conversation detail - shows messages with a specific client"""
    from messaging.models import Conversation, Message
    from messaging.forms import MessageForm
    
    conversation = get_object_or_404(Conversation, pk=pk, owner=request.user)
    
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()
            conversation.save()
            
            # Notify client
            Notification.objects.create(
                user=conversation.buyer,
                title="Nouveau message",
                message=msg.body[:120],
                notification_type="systeme",
                link=f"/dashboard/client/messagerie/{pk}/",
            )
            return redirect("dashboard:owner_conversation_detail", pk=pk)
    else:
        form = MessageForm()
    
    # Mark messages as read
    conversation.messages.exclude(sender=request.user).update(is_read=True)
    
    # Ensure session has correct dash_role
    request.session["dash_role"] = "owner"
    
    context = {
        "conversation": conversation,
        "form": form,
        "active": "messaging",
        "dash_role": "owner",
    }
    return render(request, "messaging/conversation_detail.html", context)
