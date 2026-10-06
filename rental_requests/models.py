# Modèles pour la gestion des demandes de location/achat dans DOMIORA
# Ce fichier gère les demandes de location, achat et visite de propriétés

from django.db import models
from django.conf import settings


class PropertyRequest(models.Model):
    """
    Modèle représentant une demande concernant une propriété
    Peut être une demande de location, d'achat ou de visite
    """
    class RequestType(models.TextChoices):
        """Types de demandes disponibles"""
        LOCATION = "location", "Demande de location"
        ACHAT = "achat", "Demande d'achat"
        VISITE = "visite", "Demande de visite"

    class Status(models.TextChoices):
        """Statuts possibles d'une demande"""
        EN_ATTENTE = "en_attente", "En attente"
        ACCEPTEE = "acceptee", "Acceptée"
        REJETEE = "rejetee", "Rejetée"

    # Participants
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="property_requests")  # Utilisateur qui fait la demande
    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="requests")  # Propriété concernée
    agent = models.ForeignKey("agents.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="received_requests")  # Agent concerné (optionnel)
    
    # Détails de la demande
    request_type = models.CharField(max_length=10, choices=RequestType.choices, default=RequestType.VISITE)  # Type de demande
    message = models.TextField(blank=True)  # Message de la demande
    move_in_date = models.DateField(null=True, blank=True)  # Date d'emménagement (pour les locations)
    
    # Statut et horodatage
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EN_ATTENTE)  # Statut actuel
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création
    updated_at = models.DateTimeField(auto_now=True)  # Date de dernière modification

    class Meta:
        ordering = ["-created_at"]  # Tri par date de création décroissante

    def save(self, *args, **kwargs):
        """Surcharge de la méthode save pour éventuelles logiques supplémentaires"""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.property.title} ({self.user})"
