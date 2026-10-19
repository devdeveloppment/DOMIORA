"""Cycle de vie simulé des abonnements propriétaires (aucune transaction réelle)."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import OwnerSubscription, SubscriptionEvent

S = OwnerSubscription.Status


class SubscriptionError(Exception):
    pass


def subscriptions_enabled():
    return bool(getattr(settings, "OWNER_SUBSCRIPTIONS_ENABLED", False))


def subscription_required_for(owner):
    """
    Point d'extension unique pour un futur contrôle de publication.
    Retourne toujours False tant que la fonctionnalité n'est pas activée : aucun
    propriétaire existant n'est bloqué. Non branché sur la publication actuelle.
    """
    if not subscriptions_enabled():
        return False
    return not OwnerSubscription.objects.filter(owner=owner, status__in=[S.TRIAL, S.ACTIVE],
                                                current_period_end__gte=timezone.now()).exists()


def _log(sub, action, previous, note=""):
    SubscriptionEvent.objects.create(subscription=sub, action=action, from_status=previous,
                                     to_status=sub.status, note=note)


def _transition(sub, action, allowed, to_status, note="", **fields):
    if sub.status not in allowed:
        raise SubscriptionError(f"« {action} » impossible depuis « {sub.get_status_display()} »")
    previous = sub.status
    sub.status = to_status
    for k, v in fields.items():
        setattr(sub, k, v)
    sub.save()
    _log(sub, action, previous, note)
    return sub


def simulate_start(owner, plan):
    now = timezone.now()
    trial = plan.trial_days > 0
    sub = OwnerSubscription.objects.create(
        owner=owner, plan=plan, is_simulated=True, started_at=now,
        status=S.TRIAL if trial else S.ACTIVE,
        current_period_end=now + timedelta(days=plan.trial_days if trial else plan.period_days),
    )
    _log(sub, "start", "", "Simulation — aucun prélèvement")
    return sub


def simulate_renewal(sub, success=True):
    if not success:
        return _transition(sub, "renewal_failed", {S.TRIAL, S.ACTIVE}, S.RENEWAL_FAILED, "Échec simulé")
    return _transition(sub, "renew", {S.TRIAL, S.ACTIVE, S.RENEWAL_FAILED}, S.ACTIVE, "Renouvellement simulé",
                       current_period_end=max(sub.current_period_end, timezone.now()) + timedelta(days=sub.plan.period_days))


def simulate_cancel(sub):
    return _transition(sub, "cancel", {S.TRIAL, S.ACTIVE, S.RENEWAL_FAILED}, S.CANCELED,
                       canceled_at=timezone.now(), auto_renew=False)


def expire_due(now=None):
    """Passe en « expiré » les abonnements dont la période est terminée."""
    now = now or timezone.now()
    count = 0
    for sub in OwnerSubscription.objects.filter(status__in=[S.TRIAL, S.ACTIVE, S.RENEWAL_FAILED], current_period_end__lt=now):
        _transition(sub, "expire", {S.TRIAL, S.ACTIVE, S.RENEWAL_FAILED}, S.EXPIRED)
        count += 1
    return count
