from django.db import models
from django.conf import settings


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        VENTE = "vente", "Vente"
        LOCATION = "location", "Location"

    class Status(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ANNULEE = "annulee", "Annulée"

    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="transactions")
    agent = models.ForeignKey("agents.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, default=TransactionType.VENTE)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TERMINEE)
    transaction_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date"]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.property.title} - ${self.amount:,.0f}"
