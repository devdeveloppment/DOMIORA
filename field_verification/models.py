"""
Missions de vérification de terrain.

Le vérificateur (rôle VERIFIER) contrôle sur place et transmet un rapport. Il n'a aucun
pouvoir de décision : seule une AdminDecision, créée par un administrateur, peut valider,
refuser ou demander une nouvelle vérification.

Visite de vérification ≠ visite demandée par un client (messaging.VisitRequest)
≠ visite virtuelle vidéo (properties.video).
"""
import builtins

from django.conf import settings
from django.db import models

DEFAULT_CHECKLIST = [
    ("identity_match", "La personne rencontrée correspond à la pièce d'identité fournie"),
    ("id_original_seen", "Pièce d'identité originale présentée"),
    ("ownership_docs", "Justificatif de propriété ou mandat présenté"),
    ("property_exists", "Le bien existe à l'adresse indiquée"),
    ("property_matches_listing", "Le bien correspond à la description de l'annonce"),
    ("photos_match", "Les photos de l'annonce correspondent au bien"),
    ("access_ok", "Accès au bien possible (voie, quartier)"),
]


def default_checklist():
    return [{"key": k, "label": label, "checked": False, "note": ""} for k, label in DEFAULT_CHECKLIST]


class VerificationMission(models.Model):
    class Status(models.TextChoices):
        TO_ASSIGN = "to_assign", "À attribuer"
        ASSIGNED = "assigned", "Attribuée"
        SCHEDULED = "scheduled", "Planifiée"
        IN_PROGRESS = "in_progress", "En cours"
        REPORT_SUBMITTED = "report_submitted", "Rapport soumis"
        INFO_REQUESTED = "info_requested", "Complément demandé"
        CLOSED = "closed", "Clôturée"

    class Recommendation(models.TextChoices):
        """Avis du vérificateur — purement consultatif."""
        NONE = "", "Pas d'avis"
        CONFORM = "conform", "Conforme"
        NOT_CONFORM = "not_conform", "Non conforme"
        DOUBT = "doubt", "Doute, à approfondir"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="verification_missions")
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="verification_missions")
    identity_request = models.ForeignKey("accounts.IdentityVerificationRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="missions")
    verifier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_missions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_missions")
    previous_mission = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="follow_ups")

    instructions = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TO_ASSIGN, db_index=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    checklist = models.JSONField(default=default_checklist)
    observations = models.TextField(blank=True)
    report = models.TextField(blank=True)
    recommendation = models.CharField(max_length=20, choices=Recommendation.choices, blank=True, default="")
    admin_feedback = models.TextField(blank=True, help_text="Complément demandé par l'administrateur")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mission de vérification"
        verbose_name_plural = "Missions de vérification"

    def __str__(self):
        return f"Mission #{self.pk} — {self.owner} ({self.get_status_display()})"

    @builtins.property
    def verifier_can_edit(self):
        return self.status in (self.Status.ASSIGNED, self.Status.SCHEDULED, self.Status.IN_PROGRESS, self.Status.INFO_REQUESTED)

    @builtins.property
    def latest_decision(self):
        return self.decisions.order_by("-created_at").first()


def evidence_upload_to(instance, filename):
    return f"verification_evidence/mission_{instance.mission_id}/{filename}"


class MissionEvidence(models.Model):
    class LocationSource(models.TextChoices):
        BROWSER = "browser", "Géolocalisation du navigateur (déclarative)"
        NONE = "none", "Non fournie"

    mission = models.ForeignKey(VerificationMission, on_delete=models.CASCADE, related_name="evidences")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    image = models.ImageField(upload_to=evidence_upload_to)
    caption = models.CharField(max_length=200, blank=True)
    # Métadonnées DÉCLARÉES par l'appareil : utiles mais falsifiables.
    device_captured_at = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    location_source = models.CharField(max_length=10, choices=LocationSource.choices, default=LocationSource.NONE)
    # Horodatage serveur, fiable quant au moment de réception.
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]


class MissionLog(models.Model):
    mission = models.ForeignKey(VerificationMission, on_delete=models.CASCADE, related_name="logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=40)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AdminDecision(models.Model):
    class Decision(models.TextChoices):
        VALIDATE = "validate", "Valider"
        REFUSE = "refuse", "Refuser"
        REVERIFY = "reverify", "Nouvelle vérification"

    mission = models.ForeignKey(VerificationMission, on_delete=models.CASCADE, related_name="decisions")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
