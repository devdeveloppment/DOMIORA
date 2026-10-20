import builtins

from django.conf import settings
from django.db import models

from core.private_storage import private_storage


class ListingReport(models.Model):
    """
    Signalement d'une annonce, d'un propriétaire ou d'une tentative d'arnaque.

    Un signalement ne déclenche AUCUNE sanction automatique : seul un administrateur l'examine
    et décide (dépublication éventuelle de l'annonce, décision tracée dans ReportEvent).
    """

    class Category(models.TextChoices):
        LISTING = "listing", "Annonce suspecte"
        OWNER = "owner", "Propriétaire"
        SCAM = "scam_attempt", "Tentative d'arnaque"

    class Reason(models.TextChoices):
        SCAM = "scam", "Arnaque ou tentative de fraude"
        OFF_PLATFORM_PAYMENT = "off_platform", "Demande d'argent hors plateforme"
        FAKE = "fake", "Bien inexistant ou photos trompeuses"
        WRONG_PRICE = "price", "Prix ou informations trompeurs"
        UNAVAILABLE = "unavailable", "Bien déjà loué ou vendu"
        DUPLICATE = "duplicate", "Annonce en double"
        BEHAVIOR = "behavior", "Comportement abusif ou menaçant"
        IDENTITY = "identity", "Usurpation d'identité"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        OPEN = "open", "Nouveau"
        REVIEWING = "reviewing", "En cours d'examen"
        DISMISSED = "dismissed", "Classé sans suite"
        ACTION_TAKEN = "action_taken", "Mesure prise"

    ACTIVE_STATUSES = (Status.OPEN, Status.REVIEWING)

    category = models.CharField(max_length=20, choices=Category.choices, default=Category.LISTING, db_index=True)
    # SET_NULL : le signalement et son historique survivent à la suppression de l'annonce.
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    reported_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="reports_received")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="listing_reports")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(max_length=2000, blank=True)
    attachment = models.FileField(upload_to="reports/%Y/%m/", storage=private_storage, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    admin_note = models.TextField(blank=True, help_text="Dernière note interne (historique complet dans les événements)")
    public_message = models.TextField(max_length=1000, blank=True, help_text="Message visible par l'auteur du signalement")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="handled_reports")
    handled_at = models.DateTimeField(null=True, blank=True)
    listing_unpublished = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Signalement"

    def __str__(self):
        return f"Signalement #{self.pk} — {self.property or self.reported_owner or self.get_category_display()}"

    @builtins.property  # « property » est ici le nom d'un champ
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES


class ReportEvent(models.Model):
    """Historique d'audit d'un signalement (jamais modifié ni supprimé par l'application)."""

    class Action(models.TextChoices):
        CREATED = "created", "Signalement créé"
        STATUS = "status", "Changement de statut"
        NOTE = "note", "Note interne"
        MESSAGE = "message", "Message à l'auteur"
        UNPUBLISHED = "unpublished", "Annonce dépubliée"

    report = models.ForeignKey(ListingReport, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    action = models.CharField(max_length=20, choices=Action.choices)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(max_length=2000, blank=True)
    # Seuls les événements publics (création, statut, message) sont montrés à l'auteur du signalement.
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "Événement de signalement"
