"""
Logique unique des signalements (page d'annonce et espace client passent par ici).

Règles :
- anti-abus : un seul signalement actif par (auteur, annonce) ou (auteur, propriétaire), 5 par jour ;
- confidentialité : le propriétaire visé n'est jamais notifié ni informé de l'identité de l'auteur ;
  l'auteur ne voit que les événements publics (statut, message de l'administration), jamais les notes internes ;
- aucune sanction automatique : seul `process_report` (administrateur) peut dépublier une annonce,
  et uniquement sur demande explicite avec le statut « Mesure prise ».
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from notifications.models import Notification

from .models import ListingReport, ReportEvent

MAX_REPORTS_PER_DAY = 5
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
ATTACHMENT_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",), ".pdf": (b"%PDF-",),
}
ADMIN_LINK = "/dashboard/admin-panel/signalements/{pk}/"
CLIENT_LINK = "/dashboard/client/signalements/{pk}/"


class ReportError(Exception):
    pass


def validate_attachment(upload):
    """Taille ≤ 5 Mo, extension autorisée ET signature binaire correspondante (le type MIME déclaré n'est pas fiable)."""
    if not upload:
        return None
    if upload.size > MAX_ATTACHMENT_BYTES:
        raise ReportError("Pièce jointe trop volumineuse (5 Mo maximum).")
    name = (upload.name or "").lower()
    ext = name[name.rfind("."):] if "." in name else ""
    signatures = ATTACHMENT_SIGNATURES.get(ext)
    if not signatures:
        raise ReportError("Formats acceptés : JPEG, PNG, WebP ou PDF.")
    upload.seek(0)
    head = upload.read(16)
    upload.seek(0)
    if not any(head.startswith(sig) for sig in signatures) or (ext == ".webp" and head[8:12] != b"WEBP"):
        raise ReportError("Le fichier ne correspond pas à son format déclaré.")
    return upload


def submit_report(reporter, *, reason, category=ListingReport.Category.LISTING, property_obj=None,
                  reported_owner=None, details="", attachment=None):
    if reason not in ListingReport.Reason.values:
        raise ReportError("Choisissez un motif.")
    if category not in ListingReport.Category.values:
        raise ReportError("Type de signalement inconnu.")
    if property_obj is not None and reported_owner is None:
        reported_owner = property_obj.owner
    if category == ListingReport.Category.LISTING and property_obj is None:
        raise ReportError("Choisissez l'annonce concernée.")
    if category == ListingReport.Category.OWNER and reported_owner is None:
        raise ReportError("Choisissez le propriétaire concerné.")
    if reported_owner is not None and reported_owner.pk == reporter.pk:
        raise ReportError("Vous ne pouvez pas vous signaler vous-même.")
    details = (details or "").strip()[:2000]
    if category == ListingReport.Category.SCAM and len(details) < 20:
        raise ReportError("Décrivez la tentative d'arnaque (20 caractères minimum).")

    active = ListingReport.objects.filter(reporter=reporter, status__in=ListingReport.ACTIVE_STATUSES)
    if property_obj is not None and active.filter(property=property_obj).exists():
        raise ReportError("Votre signalement pour cette annonce est déjà en cours d'examen.")
    if property_obj is None and reported_owner is not None and active.filter(reported_owner=reported_owner, property__isnull=True).exists():
        raise ReportError("Votre signalement pour ce propriétaire est déjà en cours d'examen.")
    if ListingReport.objects.filter(reporter=reporter, created_at__gte=timezone.now() - timedelta(days=1)).count() >= MAX_REPORTS_PER_DAY:
        raise ReportError("Trop de signalements aujourd'hui. Réessayez demain.")
    validate_attachment(attachment)

    with transaction.atomic():
        report = ListingReport.objects.create(
            reporter=reporter, category=category, reason=reason, property=property_obj,
            reported_owner=reported_owner, details=details,
        )
        if attachment:
            report.attachment.save(f"signalement-{report.pk}{attachment.name[attachment.name.rfind('.'):].lower()}", attachment, save=True)
        ReportEvent.objects.create(report=report, actor=reporter, action=ReportEvent.Action.CREATED,
                                   to_status=report.status, is_public=True)
        target = property_obj.title if property_obj else (
            reported_owner.get_full_name() or reported_owner.username if reported_owner else report.get_category_display())
        Notification.objects.bulk_create([
            Notification(user=admin, title="Annonce signalée" if category == ListingReport.Category.LISTING else "Nouveau signalement",
                         message=f"{report.get_category_display()} — {target} — {report.get_reason_display()}",
                         notification_type="systeme", link=ADMIN_LINK.format(pk=report.pk))
            for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True)
        ])
    return report


def process_report(report, admin_user, *, status=None, internal_note="", public_message="", unpublish=False):
    """Traitement administratif : chaque changement est tracé ; l'auteur est notifié des changements publics."""
    if admin_user.role != User.Role.ADMIN and not admin_user.is_superuser:
        raise ReportError("Action réservée à l'administration.")
    if status and status not in (ListingReport.Status.REVIEWING, ListingReport.Status.DISMISSED, ListingReport.Status.ACTION_TAKEN):
        raise ReportError("Statut inconnu.")
    if unpublish and status != ListingReport.Status.ACTION_TAKEN:
        raise ReportError("La dépublication n'est possible qu'avec la décision « Mesure prise ».")
    internal_note, public_message = internal_note.strip()[:2000], public_message.strip()[:1000]
    if not (status or internal_note or public_message):
        raise ReportError("Aucune modification à enregistrer.")

    notify = False
    with transaction.atomic():
        report = ListingReport.objects.select_for_update().get(pk=report.pk)
        previous = report.status
        if internal_note:
            report.admin_note = internal_note
            ReportEvent.objects.create(report=report, actor=admin_user, action=ReportEvent.Action.NOTE, note=internal_note)
        if status and status != previous:
            report.status = status
            report.handled_by, report.handled_at = admin_user, timezone.now()
            ReportEvent.objects.create(report=report, actor=admin_user, action=ReportEvent.Action.STATUS,
                                       from_status=previous, to_status=status, is_public=True)
            notify = True
        if public_message:
            report.public_message = public_message
            ReportEvent.objects.create(report=report, actor=admin_user, action=ReportEvent.Action.MESSAGE,
                                       note=public_message, is_public=True)
            notify = True
        if unpublish and report.property_id and not report.listing_unpublished:
            from properties.models import Property

            Property.objects.filter(pk=report.property_id).update(is_published=False)
            report.listing_unpublished = True
            ReportEvent.objects.create(report=report, actor=admin_user, action=ReportEvent.Action.UNPUBLISHED)
        report.save()
        if notify and report.reporter_id:
            text = f"Statut : {report.get_status_display()}."
            if public_message:
                text += f" Message de l'équipe : {public_message[:200]}"
            Notification.objects.create(user=report.reporter, title=f"Votre signalement #{report.pk}", message=text,
                                        notification_type="systeme", link=CLIENT_LINK.format(pk=report.pk))
    return report


def reportable_targets(client):
    """
    Annonces et propriétaires qu'un client peut choisir dans le formulaire : uniquement ceux avec
    lesquels il a interagi (consultation, favori, question, mise en relation, conversation).
    Évite d'exposer la liste de tous les propriétaires de la plateforme.
    """
    from favorites.models import Favorite
    from messaging.models import Conversation, ListingInquiry
    from properties.models import Property, PropertyUnlock, PropertyView

    prop_ids = set(PropertyView.objects.filter(user=client).values_list("property_id", flat=True)[:200])
    prop_ids |= set(Favorite.objects.filter(user=client).values_list("property_id", flat=True))
    prop_ids |= set(PropertyUnlock.objects.filter(user=client).values_list("property_id", flat=True))
    prop_ids |= set(ListingInquiry.objects.filter(client=client).values_list("property_id", flat=True))
    prop_ids |= set(Conversation.objects.filter(buyer=client, property__isnull=False).values_list("property_id", flat=True))
    properties = Property.objects.filter(pk__in=prop_ids).exclude(owner=client).select_related("owner").order_by("title")
    owner_ids = {p.owner_id for p in properties if p.owner_id}
    owner_ids |= set(Conversation.objects.filter(buyer=client).values_list("owner_id", flat=True))
    owners = User.objects.filter(pk__in=owner_ids, role=User.Role.OWNER).exclude(pk=client.pk).order_by("first_name", "username")
    return properties, owners
