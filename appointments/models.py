# Modèles pour la gestion des rendez-vous dans DOMIORA
# Ce fichier gère les rendez-vous entre utilisateurs et agents immobiliers

from django.db import models
from django.conf import settings


class Appointment(models.Model):
    """
    Modèle représentant un rendez-vous entre un utilisateur et un agent immobilier
    Peut être lié à une propriété spécifique ou être général
    """
    class Status(models.TextChoices):
        """Statuts possibles d'un rendez-vous"""
        EN_ATTENTE = "en_attente", "En attente"
        CONFIRME = "confirme", "Confirmé"
        ANNULE = "annule", "Annulé"
        TERMINE = "termine", "Terminé"

    # Participants
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")  # Utilisateur (client)
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="appointments")  # Agent immobilier
    
    # Contexte du rendez-vous
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")  # Propriété concernée (optionnel)
    scheduled_at = models.DateTimeField()  # Date et heure du rendez-vous
    notes = models.TextField(blank=True)  # Notes additionnelles
    
    # Statut et horodatage
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EN_ATTENTE)  # Statut actuel
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création

    class Meta:
        ordering = ["scheduled_at"]  # Tri par date de rendez-vous

    def __str__(self):
        return f"RDV {self.user} avec {self.agent} le {self.scheduled_at:%d/%m/%Y %H:%M}"
