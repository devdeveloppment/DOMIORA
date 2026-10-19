from django.conf import settings
from django.db import models


class ListingReport(models.Model):
    """Signalement d'une annonce suspecte. Seul un administrateur le traite."""

    class Reason(models.TextChoices):
        SCAM = "scam", "Arnaque ou tentative de fraude"
        OFF_PLATFORM_PAYMENT = "off_platform", "Demande d'argent hors plateforme"
        FAKE = "fake", "Bien inexistant ou photos trompeuses"
        WRONG_PRICE = "price", "Prix ou informations trompeurs"
        UNAVAILABLE = "unavailable", "Bien déjà loué ou vendu"
        DUPLICATE = "duplicate", "Annonce en double"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        OPEN = "open", "Nouveau"
        REVIEWING = "reviewing", "En cours d'examen"
        DISMISSED = "dismissed", "Classé sans suite"
        ACTION_TAKEN = "action_taken", "Mesure prise"

    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="listing_reports")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    admin_note = models.TextField(blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="handled_reports")
    handled_at = models.DateTimeField(null=True, blank=True)
    listing_unpublished = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Signalement"

    def __str__(self):
        return f"Signalement #{self.pk} — {self.property}"
