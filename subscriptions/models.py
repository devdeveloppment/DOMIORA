from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from agents.models import Agent

class SubscriptionPlan(models.Model):
    name = models.CharField(_("Nom"), max_length=50, unique=True, help_text="Ex: Gratuit, Standard, Professionnel, Premium")
    slug = models.SlugField(unique=True)
    price = models.DecimalField(_("Prix"), max_digits=10, decimal_places=2, default=0.00, help_text="Prix mensuel en USD ou FCFA")
    currency = models.CharField(_("Devise"), max_length=10, default="USD", help_text="USD, EUR, XOF, etc.")
    max_listings = models.IntegerField(_("Nombre d'annonces max"), default=5, help_text="Nombre maximum d'annonces. -1 pour illimité.")
    duration_days = models.PositiveIntegerField(_("Durée en jours"), default=30, help_text="Durée de validité en jours")
    features = models.JSONField(_("Fonctionnalités"), blank=True, default=dict, help_text="Liste des fonctionnalités sous forme de JSON")
    is_active = models.BooleanField(_("Actif"), default=True)
    is_recommended = models.BooleanField(_("Recommandé"), default=False)
    order = models.PositiveIntegerField(_("Ordre"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Plan d'abonnement")
        verbose_name_plural = _("Plans d'abonnement")
        ordering = ['order', 'price']

    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}"


class AgentSubscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Actif')
        PENDING = 'pending', _('En attente de paiement')
        EXPIRED = 'expired', _('Expiré')
        SUSPENDED = 'suspended', _('Suspendu')
        CANCELLED = 'cancelled', _('Annulé')

    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.RESTRICT)
    status = models.CharField(_("Statut"), max_length=20, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateTimeField(_("Date de début"), default=timezone.now)
    end_date = models.DateTimeField(_("Date de fin"), null=True, blank=True)
    auto_renew = models.BooleanField(_("Renouvellement automatique"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Abonnement de {self.agent.user.get_full_name()} - {self.plan.name}"


class PaymentHistory(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'success', _('Succès')
        FAILED = 'failed', _('Échoué')
        PENDING = 'pending', _('En attente')

    subscription = models.ForeignKey(AgentSubscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(_("Montant"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("Devise"), max_length=10, default="USD")
    payment_date = models.DateTimeField(_("Date de paiement"), default=timezone.now)
    payment_method = models.CharField(_("Méthode"), max_length=50, blank=True, help_text="ex: Stripe, Mobile Money, Virement")
    transaction_id = models.CharField(_("ID Transaction"), max_length=100, blank=True)
    status = models.CharField(_("Statut"), max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Historique de paiement")
        verbose_name_plural = _("Historiques de paiement")
        ordering = ['-payment_date']

    def __str__(self):
        return f"Paiement de {self.amount} {self.currency} - {self.subscription.agent.user.get_full_name()}"

