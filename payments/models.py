"""
Paiements de mise en relation client ↔ propriétaire.

Responsabilités distinctes :
- PaymentAttempt : une tentative de paiement des frais de mise en relation (aucune donnée bancaire).
- PaymentEvent   : journal idempotent des notifications/vérifications reçues pour une tentative.
- La relation client ↔ propriétaire reste matérialisée par properties.PropertyUnlock
  (voir payments.relations) ; transactions.Transaction concerne les ventes/locations
  immobilières et n'est pas liée à ces frais.
"""
import builtins
import uuid

from django.conf import settings
from django.db import models


class PaymentAttempt(models.Model):
    class Provider(models.TextChoices):
        SIMULATION = "simulation", "Simulation (démonstration)"
        FEDAPAY = "fedapay", "FedaPay"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Payé"
        DECLINED = "declined", "Refusé"
        CANCELED = "canceled", "Annulé"
        EXPIRED = "expired", "Expiré"
        FAILED = "failed", "Échec technique"

    TERMINAL_STATUSES = {Status.APPROVED, Status.DECLINED, Status.CANCELED, Status.EXPIRED, Status.FAILED}

    class SimulatedOutcome(models.TextChoices):
        """État côté « fournisseur » simulé, fixé uniquement par l'interface de démonstration."""
        NONE = "", "Aucun choix"
        APPROVED = "approved", "Paiement réussi"
        DECLINED = "declined", "Paiement refusé"
        CANCELED = "canceled", "Paiement annulé"
        PENDING = "pending", "Paiement en attente"
        TIMEOUT = "timeout", "Délai dépassé"
        ERROR = "error", "Erreur technique"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact_payments")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_contact_payments")
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="contact_payments")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    simulated_outcome = models.CharField(max_length=20, choices=SimulatedOutcome.choices, blank=True, default="")
    last_error = models.CharField(max_length=255, blank=True)
    relation_granted = models.BooleanField(default=False)
    # Paiement de test (simulation ou FedaPay sandbox) : jamais compté comme revenu encaissé.
    is_test = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["client", "owner", "status"])]
        verbose_name = "Tentative de paiement"
        verbose_name_plural = "Tentatives de paiement"

    def __str__(self):
        return f"{self.reference} — {self.client} → {self.owner} ({self.get_status_display()})"

    @builtins.property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    @builtins.property
    def is_simulation(self):
        return self.provider == self.Provider.SIMULATION


class PaymentEvent(models.Model):
    class Source(models.TextChoices):
        RETURN = "return", "Retour utilisateur (vérification serveur)"
        WEBHOOK = "webhook", "Notification fournisseur"
        SIMULATOR = "simulator", "Interface de démonstration"
        SYSTEM = "system", "Système"

    attempt = models.ForeignKey(PaymentAttempt, on_delete=models.CASCADE, related_name="events")
    # Clé d'idempotence : une même notification reçue deux fois n'est traitée qu'une fois.
    event_key = models.CharField(max_length=150, unique=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    reported_status = models.CharField(max_length=30, blank=True)
    status_before = models.CharField(max_length=20, blank=True)
    status_after = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at"]
        verbose_name = "Événement de paiement"
        verbose_name_plural = "Événements de paiement"

    def __str__(self):
        return f"{self.attempt.reference} {self.source}:{self.reported_status}"
