"""
Abonnements propriétaires — architecture préparée, NON ACTIVÉE.

- Distinct de la relation payante client ↔ propriétaire (payments) et des transactions
  immobilières (transactions.Transaction).
- Aucun tarif, quota ni avantage n'est défini : les plans créés ici sont des plans de
  démonstration (is_demo=True) ou des brouillons sans prix.
- Tant que settings.OWNER_SUBSCRIPTIONS_ENABLED est False, rien n'est exigé des
  propriétaires (voir services.subscription_required_for).
- Aucun prélèvement : le cycle de vie se simule (services.simulate_*).
"""
from django.conf import settings
from django.db import models


class Plan(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    # Prix volontairement facultatif : aucun tarif validé à ce jour.
    price_xof = models.PositiveIntegerField(null=True, blank=True)
    period_days = models.PositiveIntegerField(default=30)
    trial_days = models.PositiveIntegerField(default=0)
    # Limites éventuelles (ex. {"max_active_listings": 5}) — vides tant que non validées.
    limits = models.JSONField(default=dict, blank=True)
    is_demo = models.BooleanField(default=True, help_text="Plan de démonstration, sans valeur commerciale")
    is_active = models.BooleanField(default=False, help_text="Proposable aux propriétaires (après validation métier)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}{' (démo)' if self.is_demo else ''}"


class OwnerSubscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "En essai"
        ACTIVE = "active", "Actif"
        RENEWAL_FAILED = "renewal_failed", "Renouvellement échoué"
        EXPIRED = "expired", "Expiré"
        CANCELED = "canceled", "Annulé"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owner_subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    is_simulated = models.BooleanField(default=True)
    started_at = models.DateTimeField()
    current_period_end = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SubscriptionEvent(models.Model):
    subscription = models.ForeignKey(OwnerSubscription, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=30)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
