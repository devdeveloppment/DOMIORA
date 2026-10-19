"""
Règles des abonnements (toutes appliquées côté serveur).

Souscription
- Plan gratuit : actif immédiatement, sans échéance.
- Plan payant, essai disponible (SUBSCRIPTION_TRIAL_DAYS > 0, jamais utilisé) : essai immédiat,
  aucune transaction ; à la fin de l'essai l'abonnement expire sauf paiement (renouvellement).
- Plan payant sans essai : abonnement « en attente » + transaction fictive ; il n'est activé
  qu'après une décision « réussi » du simulateur, enregistrée côté serveur.
Changement de plan
- Vers un plan supérieur : nouvelle transaction ; à son succès, l'ancien abonnement est
  « remplacé » et le nouveau démarre (pas de prorata).
- Vers un plan inférieur ou gratuit : programmé à l'échéance (scheduled_plan).
Annulation : plus de renouvellement ; avantages conservés jusqu'à l'échéance, puis « annulé ».
Renouvellement simulé : transaction fictive ; au succès, échéance prolongée d'une période.
Échéances : `manage.py process_owner_subscriptions` (idempotent).
"""
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import OwnerSubscription, Plan, SubscriptionEvent, SubscriptionPayment

S = OwnerSubscription.Status
P = SubscriptionPayment.Status


class SubscriptionError(Exception):
    pass


def subscriptions_enabled():
    return bool(getattr(settings, "OWNER_SUBSCRIPTIONS_ENABLED", False))


def subscription_required_for(owner):
    """Aucun abonnement payant n'est exigé pour publier (décision non prise) : toujours False."""
    return False


def _log(sub, action, previous, note=""):
    SubscriptionEvent.objects.create(subscription=sub, action=action, from_status=previous or "",
                                     to_status=sub.status, note=note[:255])


def _set(sub, action, status, note="", **fields):
    previous = sub.status
    sub.status = status
    for k, v in fields.items():
        setattr(sub, k, v)
    sub.save()
    _log(sub, action, previous, note)
    return sub


def _lock_owner(owner):
    from accounts.models import User

    return User.objects.select_for_update().get(pk=owner.pk)


def current_subscription(owner, now=None):
    now = now or timezone.now()
    sub = (OwnerSubscription.objects.select_related("plan", "scheduled_plan")
           .filter(owner=owner, status__in=OwnerSubscription.CURRENT).first())
    if sub and sub.current_period_end and sub.current_period_end <= now:
        return None  # échu, en attente du traitement des échéances : plus d'avantages
    return sub


def free_plan():
    return Plan.objects.filter(price_xof=0, is_active=True).order_by("order").first()


def active_plan(owner, now=None):
    """Plan dont les avantages s'appliquent maintenant (gratuit par défaut)."""
    if not subscriptions_enabled():
        return None
    sub = current_subscription(owner, now)
    return sub.plan if sub else free_plan()


def _check_owner(owner):
    if getattr(owner, "role", None) != "owner" or not owner.is_active:
        raise SubscriptionError("Les abonnements sont réservés aux propriétaires et agents immobiliers.")


def trial_available(owner):
    """Essai : activé, durée > 0, compte inscrit après la date d'éligibilité, jamais utilisé."""
    from datetime import date

    if not settings.SUBSCRIPTION_TRIAL_ENABLED or settings.SUBSCRIPTION_TRIAL_DAYS <= 0:
        return False
    try:
        since = date.fromisoformat(settings.SUBSCRIPTION_TRIAL_ELIGIBLE_FROM)
    except (TypeError, ValueError):
        return False  # aucune date : aucun compte éligible (jamais d'activation rétroactive)
    if timezone.localdate(owner.date_joined) < since:
        return False
    return not OwnerSubscription.objects.filter(owner=owner, trial_used=True).exists()


_trial_available = trial_available


def _new_payment(sub, plan, purpose):
    return SubscriptionPayment.objects.create(subscription=sub, owner=sub.owner, plan=plan, purpose=purpose,
                                              amount=plan.price_xof, currency="XOF")


@transaction.atomic
def subscribe(owner, plan_code):
    """Retourne (abonnement, transaction_fictive_ou_None)."""
    if not subscriptions_enabled():
        raise SubscriptionError("Les abonnements ne sont pas encore ouverts.")
    _check_owner(owner)
    _lock_owner(owner)  # sérialise les demandes simultanées d'un même propriétaire
    plan = Plan.objects.filter(code=plan_code).first()
    if plan is None or not plan.is_purchasable:
        raise SubscriptionError("Ce plan n'est pas disponible.")
    now = timezone.now()
    current = current_subscription(owner, now)

    if current and current.plan_id == plan.pk:
        if current.cancel_at_period_end:
            current.cancel_at_period_end = False
            current.auto_renew = True
            current.scheduled_plan = None
            current.save()
            _log(current, "resume", current.status, "Annulation retirée")
        return current, None

    # Passage vers un plan inférieur : programmé à l'échéance.
    if current and current.current_period_end and (plan.price_xof or 0) < (current.plan.price_xof or 0):
        current.scheduled_plan = plan
        current.save(update_fields=["scheduled_plan", "updated_at"])
        _log(current, "schedule_downgrade", current.status, f"Vers {plan.name} à l'échéance")
        return current, None

    if plan.is_free:
        if current:
            _set(current, "supersede", S.SUPERSEDED, f"Remplacé par {plan.name}")
        sub = OwnerSubscription.objects.create(owner=owner, plan=plan, status=S.ACTIVE, started_at=now)
        _log(sub, "start_free", "")
        return sub, None

    if _trial_available(owner) and current is None:
        sub = OwnerSubscription.objects.create(
            owner=owner, plan=plan, status=S.TRIAL, started_at=now, trial_used=True,
            current_period_end=now + timedelta(days=settings.SUBSCRIPTION_TRIAL_DAYS))
        _log(sub, "start_trial", "", f"Essai de {settings.SUBSCRIPTION_TRIAL_DAYS} jour(s)")
        return sub, None

    # Une seule demande en attente : on la réutilise si elle vise le même plan.
    pending = OwnerSubscription.objects.filter(owner=owner, status=S.PENDING).first()
    if pending and pending.plan_id != plan.pk:
        _set(pending, "abandon", S.CANCELED, "Remplacée par une nouvelle demande")
        pending.payments.filter(status=P.PENDING).update(status=P.CANCELED, decided_at=now)
        pending = None
    if pending is None:
        pending = OwnerSubscription.objects.create(owner=owner, plan=plan, status=S.PENDING)
        _log(pending, "request", "")
    payment = pending.payments.filter(status=P.PENDING).first() or _new_payment(
        pending, plan, SubscriptionPayment.Purpose.UPGRADE if current else SubscriptionPayment.Purpose.NEW)
    return pending, payment


@transaction.atomic
def request_renewal(owner):
    _check_owner(owner)
    _lock_owner(owner)
    sub = OwnerSubscription.objects.filter(owner=owner, status__in=OwnerSubscription.CURRENT).select_related("plan").first()
    if sub is None or sub.plan.is_free:
        raise SubscriptionError("Aucun abonnement payant à renouveler.")
    existing = sub.payments.filter(status=P.PENDING, purpose=SubscriptionPayment.Purpose.RENEWAL).first()
    return existing or _new_payment(sub, sub.plan, SubscriptionPayment.Purpose.RENEWAL)


@transaction.atomic
def cancel(owner):
    _check_owner(owner)
    sub = OwnerSubscription.objects.select_for_update().filter(owner=owner, status__in=OwnerSubscription.CURRENT).first()
    if sub is None or sub.plan.is_free:
        raise SubscriptionError("Aucun abonnement payant à annuler.")
    if sub.cancel_at_period_end:
        return sub
    sub.cancel_at_period_end = True
    sub.auto_renew = False
    sub.canceled_at = timezone.now()
    sub.save()
    _log(sub, "cancel", sub.status, "Avantages conservés jusqu'à l'échéance")
    return sub


@transaction.atomic
def decide_payment(owner, reference, outcome):
    """
    Décision du simulateur (succeeded/failed/canceled/pending), appliquée côté serveur.
    Idempotente : une transaction déjà tranchée ne change plus.
    """
    if outcome not in ("succeeded", "failed", "canceled", "pending"):
        raise SubscriptionError("Scénario inconnu.")
    _lock_owner(owner)
    payment = (SubscriptionPayment.objects.select_for_update().select_related("subscription", "plan")
               .filter(reference=reference, owner=owner).first())
    if payment is None:
        raise SubscriptionError("Transaction introuvable.")
    if payment.status in SubscriptionPayment.TERMINAL or outcome == "pending":
        return payment
    now = timezone.now()
    payment.status = outcome
    payment.decided_at = now
    payment.save(update_fields=["status", "decided_at"])
    sub = payment.subscription
    if outcome != "succeeded":
        if sub.status == S.PENDING:
            _set(sub, f"payment_{outcome}", S.CANCELED if outcome == "canceled" else S.PENDING,
                 f"Transaction fictive {payment.reference}")
        else:
            _log(sub, f"renewal_{outcome}", sub.status, f"Transaction fictive {payment.reference}")
        return payment

    period = timedelta(days=payment.plan.period_days)
    if payment.purpose == SubscriptionPayment.Purpose.RENEWAL:
        base = max(sub.current_period_end or now, now)
        _set(sub, "renew", S.ACTIVE, f"Transaction fictive {payment.reference}", current_period_end=base + period,
             cancel_at_period_end=False, auto_renew=True)
        return payment
    current = OwnerSubscription.objects.filter(owner=owner, status__in=OwnerSubscription.CURRENT).exclude(pk=sub.pk).first()
    if current:
        _set(current, "supersede", S.SUPERSEDED, f"Remplacé par {payment.plan.name}")
    try:
        with transaction.atomic():
            _set(sub, "activate", S.ACTIVE, f"Transaction fictive {payment.reference}", started_at=now,
                 current_period_end=now + period)
    except IntegrityError:
        raise SubscriptionError("Un abonnement est déjà actif.")
    return payment


def process_due(now=None):
    """Traite les échéances. Idempotent : relancer ne change rien de plus."""
    now = now or timezone.now()
    done = 0
    due = OwnerSubscription.objects.filter(status__in=OwnerSubscription.CURRENT, current_period_end__lte=now).select_related("plan", "scheduled_plan")
    for sub in due:
        with transaction.atomic():
            sub = OwnerSubscription.objects.select_for_update().get(pk=sub.pk)
            if sub.status not in OwnerSubscription.CURRENT or not sub.current_period_end or sub.current_period_end > now:
                continue
            scheduled = sub.scheduled_plan
            _set(sub, "period_end", S.CANCELED if sub.cancel_at_period_end else S.EXPIRED)
            if scheduled and scheduled.is_free:
                new = OwnerSubscription.objects.create(owner=sub.owner, plan=scheduled, status=S.ACTIVE, started_at=now)
                _log(new, "start_free", "", "Plan programmé à l'échéance")
            elif scheduled:
                new = OwnerSubscription.objects.create(owner=sub.owner, plan=scheduled, status=S.PENDING)
                _new_payment(new, scheduled, SubscriptionPayment.Purpose.NEW)
                _log(new, "request", "", "Plan programmé : paiement requis")
            if not (scheduled and scheduled.is_free):
                # Fin d'essai ou d'abonnement : retour explicite au plan gratuit (sans échéance).
                fp = free_plan()
                if fp and not OwnerSubscription.objects.filter(owner=sub.owner, status__in=OwnerSubscription.CURRENT).exists():
                    new_free = OwnerSubscription.objects.create(owner=sub.owner, plan=fp, status=S.ACTIVE, started_at=now)
                    _log(new_free, "start_free", "", "Retour au plan gratuit après échéance")
            done += 1
    return done


# Compatibilité avec la première version (tests, commande expire_owner_subscriptions).
def expire_due(now=None):
    return process_due(now)
