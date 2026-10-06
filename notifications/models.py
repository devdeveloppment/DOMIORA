# Modèle pour la gestion des notifications dans DOMIORA
# Ce fichier permet d'envoyer des notifications aux utilisateurs pour divers événements

from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    Représente une notification système envoyée à un utilisateur.
    Elle sert à informer sur les événements importants du site : messages, vérifications,
    transactions, demandes, mises à jour de statut, etc.
    """
    class NotifType(models.TextChoices):
        """Types de notifications disponibles dans le système"""
        INFO = "info", "Info"  # Information générale
        DEMANDE = "demande", "Nouvelle demande"  # Nouvelle demande (visite, rendez-vous, etc.)
        TRANSACTION = "transaction", "Transaction"  # Notification liée aux transactions
        SYSTEME = "systeme", "Système"  # Notification système
        VERIFICATION_APPROVED = "verification_approved", "Validation identité"  # Identité approuvée
        VERIFICATION_REJECTED = "verification_rejected", "Refus identité"  # Identité rejetée

    # Champs principaux
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")  # Destinataire de la notification
    title = models.CharField(max_length=200)  # Titre de la notification
    message = models.TextField(blank=True)  # Message détaillé
    notification_type = models.CharField(max_length=30, choices=NotifType.choices, default=NotifType.INFO)  # Type de notification
    link = models.CharField(max_length=255, blank=True)  # Lien vers la page concernée
    is_read = models.BooleanField(default=False)  # Statut de lecture
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création

    class Meta:
        ordering = ["-created_at"]  # Tri par date décroissante

    def __str__(self):
        return self.title
