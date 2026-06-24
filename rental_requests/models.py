from django.db import models
from django.conf import settings


class PropertyRequest(models.Model):
    class RequestType(models.TextChoices):
        LOCATION = "location", "Demande de location"
        ACHAT = "achat", "Demande d'achat"
        VISITE = "visite", "Demande de visite"

    class Status(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        ACCEPTEE = "acceptee", "Acceptée"
        REJETEE = "rejetee", "Rejetée"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="property_requests")
    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="requests")
    agent = models.ForeignKey("agents.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="received_requests")
    request_type = models.CharField(max_length=10, choices=RequestType.choices, default=RequestType.VISITE)
    message = models.TextField(blank=True)
    move_in_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EN_ATTENTE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.agent_id and self.property_id:
            self.agent = self.property.agent
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.property.title} ({self.user})"
