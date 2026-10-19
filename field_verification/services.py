"""Transitions des missions. Chaque fonction vérifie l'acteur et l'état, puis journalise."""
from django.db import transaction
from django.utils import timezone

from accounts.models import IdentityVerificationRequest, User
from notifications.models import Notification

from .models import AdminDecision, MissionLog, VerificationMission

S = VerificationMission.Status
PRE_VISIT_STATUSES = {
    User.VerificationStatus.UNVERIFIED,
    User.VerificationStatus.PENDING_DOCUMENTS,
    User.VerificationStatus.PENDING_FIELD_VISIT,
    User.VerificationStatus.FIELD_VISIT_COMPLETED,
}


class TransitionError(Exception):
    pass


def _is_admin(user):
    return user.is_superuser or user.role == User.Role.ADMIN


def _log(mission, actor, action, from_status, note=""):
    MissionLog.objects.create(mission=mission, actor=actor, action=action,
                              from_status=from_status, to_status=mission.status, note=note)


def _move(mission, actor, action, allowed_from, to_status, note="", **fields):
    if mission.status not in allowed_from:
        raise TransitionError(f"Action « {action} » impossible depuis « {mission.get_status_display()} ».")
    previous = mission.status
    mission.status = to_status
    for k, v in fields.items():
        setattr(mission, k, v)
    mission.save()
    _log(mission, actor, action, previous, note)
    return mission


def _set_owner_status(owner, status):
    """Avance le statut du propriétaire pendant l'instruction, sans jamais l'approuver/le refuser."""
    if owner.verification_status in PRE_VISIT_STATUSES:
        owner.verification_status = status
        owner.save(update_fields=["verification_status"])


# --- Administrateur -------------------------------------------------------

def create_mission(admin, owner, property_obj=None, instructions="", verifier=None, previous=None):
    if not _is_admin(admin):
        raise TransitionError("Seul un administrateur crée une mission.")
    identity = owner.verification_requests.order_by("-submitted_at").first()
    mission = VerificationMission.objects.create(
        owner=owner, property=property_obj, identity_request=identity, created_by=admin,
        instructions=instructions, previous_mission=previous,
    )
    _log(mission, admin, "create", "")
    if verifier:
        assign(admin, mission, verifier)
    return mission


def assign(admin, mission, verifier):
    if not _is_admin(admin):
        raise TransitionError("Seul un administrateur attribue une mission.")
    if verifier.role != User.Role.VERIFIER or not verifier.is_active:
        raise TransitionError("La mission doit être attribuée à un vérificateur actif.")
    _move(mission, admin, "assign", {S.TO_ASSIGN, S.ASSIGNED, S.SCHEDULED}, S.ASSIGNED,
          note=f"Attribuée à {verifier.get_full_name() or verifier.username}", verifier=verifier)
    _set_owner_status(mission.owner, User.VerificationStatus.PENDING_FIELD_VISIT)
    Notification.objects.create(user=verifier, title="Nouvelle mission de vérification",
                                message="Une mission vous a été attribuée.", notification_type="systeme",
                                link=f"/dashboard/verificateur/missions/{mission.pk}/")
    return mission


def request_info(admin, mission, feedback):
    if not _is_admin(admin):
        raise TransitionError("Seul un administrateur demande un complément.")
    if not feedback.strip():
        raise TransitionError("Précisez le complément attendu.")
    _move(mission, admin, "request_info", {S.REPORT_SUBMITTED}, S.INFO_REQUESTED, note=feedback, admin_feedback=feedback)
    if mission.verifier:
        Notification.objects.create(user=mission.verifier, title="Complément demandé",
                                    message=feedback[:200], notification_type="systeme",
                                    link=f"/dashboard/verificateur/missions/{mission.pk}/")
    return mission


@transaction.atomic
def decide(admin, mission, decision, reason=""):
    """Décision finale — réservée à l'administrateur."""
    if not _is_admin(admin):
        raise TransitionError("Seul un administrateur prend la décision finale.")
    if decision not in AdminDecision.Decision.values:
        raise TransitionError("Décision inconnue.")
    if mission.status != S.REPORT_SUBMITTED:
        raise TransitionError("La décision intervient après la soumission du rapport.")
    if decision in (AdminDecision.Decision.REFUSE, AdminDecision.Decision.REVERIFY) and not reason.strip():
        raise TransitionError("Un motif est requis.")

    AdminDecision.objects.create(mission=mission, admin=admin, decision=decision, reason=reason)
    _move(mission, admin, f"decision:{decision}", {S.REPORT_SUBMITTED}, S.CLOSED, note=reason, closed_at=timezone.now())
    owner = mission.owner
    identity = mission.identity_request

    if decision == AdminDecision.Decision.VALIDATE:
        if identity and identity.status != IdentityVerificationRequest.Status.APPROVED:
            identity.approve(admin)
            owner.refresh_from_db()
        else:
            owner.verification_status = User.VerificationStatus.APPROVED
            owner.can_publish_properties = True
            owner.verification_date = timezone.now()
            owner.verification_rejection_reason = ""
        owner.field_visit_completed = mission.submitted_at
        owner.field_visit_agent = mission.verifier.get_full_name() if mission.verifier else ""
        owner.property_verified = bool(mission.property)
        owner.save()
        msg = "Votre vérification a été validée par l'administration."
    elif decision == AdminDecision.Decision.REFUSE:
        if identity:
            identity.reject(admin, reason)
            owner.refresh_from_db()
        else:
            owner.verification_status = User.VerificationStatus.REJECTED
            owner.can_publish_properties = False
            owner.verification_rejection_reason = reason
            owner.save()
        msg = f"Votre vérification a été refusée. Motif : {reason}"
    else:
        create_mission(admin, owner, mission.property, instructions=reason, previous=mission)
        msg = "Une nouvelle vérification de terrain va être programmée."
    Notification.objects.create(user=owner, title="Décision de vérification", message=msg,
                                notification_type="systeme", link="/dashboard/proprietaire/verification-identite/")
    return mission


# --- Vérificateur ---------------------------------------------------------

def _check_verifier(user, mission):
    if user.role != User.Role.VERIFIER or mission.verifier_id != user.pk:
        raise TransitionError("Cette mission ne vous est pas attribuée.")


def schedule(verifier, mission, when):
    _check_verifier(verifier, mission)
    return _move(mission, verifier, "schedule", {S.ASSIGNED, S.SCHEDULED}, S.SCHEDULED,
                 note=f"Visite prévue le {when:%d/%m/%Y %H:%M}", scheduled_for=when)


def start(verifier, mission):
    _check_verifier(verifier, mission)
    return _move(mission, verifier, "start", {S.ASSIGNED, S.SCHEDULED}, S.IN_PROGRESS, started_at=timezone.now())


def save_report(verifier, mission, checklist_updates, observations, report, recommendation):
    """Brouillon : enregistre sans changer d'état."""
    _check_verifier(verifier, mission)
    if mission.status not in (S.IN_PROGRESS, S.INFO_REQUESTED):
        raise TransitionError("Démarrez la mission avant de remplir le rapport.")
    items = []
    for item in mission.checklist:
        upd = checklist_updates.get(item["key"], {})
        items.append({**item, "checked": bool(upd.get("checked")), "note": (upd.get("note") or "")[:300]})
    mission.checklist = items
    mission.observations = observations
    mission.report = report
    if recommendation in VerificationMission.Recommendation.values:
        mission.recommendation = recommendation
    mission.save()
    return mission


def submit_report(verifier, mission):
    _check_verifier(verifier, mission)
    if not mission.report.strip():
        raise TransitionError("Le rapport ne peut pas être vide.")
    _move(mission, verifier, "submit", {S.IN_PROGRESS, S.INFO_REQUESTED}, S.REPORT_SUBMITTED, submitted_at=timezone.now())
    _set_owner_status(mission.owner, User.VerificationStatus.FIELD_VISIT_COMPLETED)
    for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True):
        Notification.objects.create(user=admin, title="Rapport de vérification soumis",
                                    message=f"Mission #{mission.pk} — {mission.owner}", notification_type="systeme",
                                    link=f"/dashboard/admin-panel/missions/{mission.pk}/")
    return mission
