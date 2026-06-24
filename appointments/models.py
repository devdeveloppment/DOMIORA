from django.db import models
from django.conf import settings


class Appointment(models.Model):
    class Status(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        CONFIRME = "confirme", "Confirmé"
        ANNULE = "annule", "Annulé"
        TERMINE = "termine", "Terminé"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="appointments")
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    scheduled_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EN_ATTENTE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"RDV {self.user} avec {self.agent} le {self.scheduled_at:%d/%m/%Y %H:%M}"
