from django.db import models
from django.utils import timezone
from agents.models import Agent

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="Ex: Gratuit, Standard, Professionnel, Premium")
    slug = models.SlugField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Prix mensuel en USD ou FCFA")
    currency = models.CharField(max_length=10, default="USD", help_text="USD, EUR, XOF, etc.")
    max_listings = models.IntegerField(default=5, help_text="Nombre maximum d'annonces. -1 pour illimité.")
    duration_days = models.PositiveIntegerField(default=30, help_text="Durée de validité en jours")
    features = models.JSONField(default=dict, blank=True, help_text="Liste des fonctionnalités sous forme de JSON")
    is_active = models.BooleanField(default=True)
    is_recommended = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "price"]
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"

    def __str__(self):
        return f"{self.name} ({self.price} {self.currency})"

class AgentSubscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Actif'
        PENDING = 'pending', 'En attente de paiement'
        EXPIRED = 'expired', 'Expiré'
        SUSPENDED = 'suspended', 'Suspendu'
        CANCELLED = 'cancelled', 'Annulé'

    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.RESTRICT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Abonnement de {self.agent} - {self.plan.name} ({self.get_status_display()})"

    @property
    def is_valid(self):
        if self.status == self.Status.ACTIVE:
            if self.end_date and self.end_date < timezone.now():
                return False
            return True
        return False

class PaymentHistory(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Succès'
        FAILED = 'failed', 'Échoué'
        PENDING = 'pending', 'En attente'

    subscription = models.ForeignKey(AgentSubscription, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=50, blank=True, help_text="ex: Stripe, Mobile Money, Virement")
    transaction_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date"]
        verbose_name = "Historique de paiement"
        verbose_name_plural = "Historiques de paiement"

    def __str__(self):
        return f"Paiement de {self.amount} {self.currency} pour {self.subscription.agent} ({self.get_status_display()})"
