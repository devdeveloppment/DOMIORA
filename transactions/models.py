# Modèles pour la gestion des transactions immobilières dans DOMIORA
# Ce fichier gère le suivi des ventes et locations avec commissions

from django.db import models
from django.conf import settings


class Transaction(models.Model):
    """
    Modèle représentant une transaction immobilière (vente ou location)
    Enregistre les détails financiers et le statut de chaque transaction
    """
    class TransactionType(models.TextChoices):
        """Types de transactions disponibles"""
        VENTE = "vente", "Vente"
        LOCATION = "location", "Location"

    class Status(models.TextChoices):
        """Statuts possibles d'une transaction"""
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ANNULEE = "annulee", "Annulée"

    # Relations avec les autres entités
    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="transactions")  # Propriété concernée
    agent = models.ForeignKey("agents.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")  # Agent immobilier (optionnel)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")  # Client (optionnel)
    
    # Détails de la transaction
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, default=TransactionType.VENTE)  # Type de transaction
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # Montant de la transaction
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Montant de la commission de l'agent
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TERMINEE)  # Statut actuel
    transaction_date = models.DateField()  # Date de la transaction
    notes = models.TextField(blank=True)  # Notes complémentaires
    created_at = models.DateTimeField(auto_now_add=True)  # Date d'enregistrement

    class Meta:
        ordering = ["-transaction_date"]  # Tri par date de transaction décroissante

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.property.title} - ${self.amount:,.0f}"
