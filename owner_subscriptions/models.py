"""
Abonnements des propriétaires et agents immobiliers (rôle owner).

- Distinct de la relation payante client ↔ propriétaire (payments) et des transactions
  immobilières (transactions.Transaction).
- Les tarifs sont des PROPOSITIONS (Plan.is_proposal) chargées depuis
  settings.SUBSCRIPTION_PLAN_PROPOSALS par `manage.py sync_subscription_plans` ; la base
  est ensuite la seule source de vérité (web, API, mobile).
- Aucun paiement réel : SubscriptionPayment est toujours simulé (environment="demo").
- Dates en UTC (USE_TZ) ; le Togo est en GMT toute l'année.
"""
import builtins
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Plan(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    # Prix mensuel envisagé (FCFA). Null = non défini : le plan ne peut pas être souscrit.
    price_xof = models.PositiveIntegerField(null=True, blank=True)
    period_days = models.PositiveIntegerField(default=30)
    # Niveau de visibilité utilisé par le classement (0 = organique uniquement).
    visibility_level = models.PositiveSmallIntegerField(default=0)
    # Nombre maximum d'annonces pouvant être mises en avant simultanément.
    max_promoted_listings = models.PositiveSmallIntegerField(default=0)
    features = models.JSONField(default=list, blank=True, help_text="Avantages affichés (liste de textes)")
    limits = models.JSONField(default=dict, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_proposal = models.BooleanField(default=True, help_text="Tarif envisagé, non validé commercialement")
    is_demo = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False, help_text="Proposé aux propriétaires")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.name

    @builtins.property
    def is_free(self):
        return self.price_xof == 0

    @builtins.property
    def is_purchasable(self):
        return self.is_active and self.price_xof is not None


class OwnerSubscription(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        TRIAL = "trial", "En essai"
        ACTIVE = "active", "Actif"
        EXPIRED = "expired", "Expiré"
        CANCELED = "canceled", "Annulé"
        SUPERSEDED = "superseded", "Remplacé par un autre plan"
        # Hérité de la première version (non utilisé par les nouveaux parcours).
        RENEWAL_FAILED = "renewal_failed", "Renouvellement échoué"

    CURRENT = (Status.TRIAL, Status.ACTIVE)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owner_subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_simulated = models.BooleanField(default=True)
    started_at = models.DateTimeField(null=True, blank=True)
    # Null pour le plan gratuit (sans échéance).
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)
    auto_renew = models.BooleanField(default=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    scheduled_plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                       help_text="Plan appliqué à l'échéance (passage à un plan inférieur)")
    trial_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Un seul abonnement en cours (essai/actif) et une seule demande en attente par propriétaire.
            models.UniqueConstraint(fields=["owner"], condition=Q(status__in=["trial", "active"]),
                                    name="one_current_subscription_per_owner"),
            models.UniqueConstraint(fields=["owner"], condition=Q(status="pending"),
                                    name="one_pending_subscription_per_owner"),
        ]

    def __str__(self):
        return f"{self.owner} — {self.plan} ({self.get_status_display()})"


class SubscriptionEvent(models.Model):
    subscription = models.ForeignKey(OwnerSubscription, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=30)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class SubscriptionPayment(models.Model):
    """Transaction FICTIVE. Jamais confondue avec un paiement réel (environment, is_simulated)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCEEDED = "succeeded", "Réussi (simulation)"
        FAILED = "failed", "Échoué (simulation)"
        CANCELED = "canceled", "Annulé (simulation)"

    class Purpose(models.TextChoices):
        NEW = "new", "Souscription"
        RENEWAL = "renewal", "Renouvellement"
        UPGRADE = "upgrade", "Changement de plan"

    TERMINAL = (Status.SUCCEEDED, Status.FAILED, Status.CANCELED)

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    subscription = models.ForeignKey(OwnerSubscription, on_delete=models.CASCADE, related_name="payments")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_payments")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.NEW)
    # Montant figé au moment de la création : jamais recalculé rétroactivement.
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_simulated = models.BooleanField(default=True)
    environment = models.CharField(max_length=10, default="demo")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[DÉMO] {self.reference} {self.amount} {self.currency} {self.get_status_display()}"
