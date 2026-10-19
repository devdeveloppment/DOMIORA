from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from dashboard.decorators import role_required

from . import services
from .models import OwnerSubscription, Plan, SubscriptionPayment

SIM_CHOICES = [
    ("succeeded", "Paiement réussi", "L'abonnement est activé."),
    ("failed", "Paiement échoué", "Aucun avantage n'est accordé."),
    ("canceled", "Paiement annulé", "Le propriétaire abandonne."),
    ("pending", "Paiement en attente", "Le fournisseur n'a pas encore répondu."),
]


@role_required(User.Role.OWNER)
def subscription_home(request):
    enabled = services.subscriptions_enabled()
    current = services.current_subscription(request.user) if enabled else None
    pending = OwnerSubscription.objects.filter(owner=request.user, status=OwnerSubscription.Status.PENDING).select_related("plan").first()
    pending_payment = pending.payments.filter(status=SubscriptionPayment.Status.PENDING).first() if pending else None
    renewal_payment = (current.payments.filter(status=SubscriptionPayment.Status.PENDING,
                                               purpose=SubscriptionPayment.Purpose.RENEWAL).first() if current else None)
    from properties.ranking import promoted_property_ids_for_owner

    return render(request, "owner_subscriptions/home.html", {
        "enabled": enabled,
        "plans": Plan.objects.filter(is_active=True) if enabled else [],
        "upcoming_plans": Plan.objects.filter(is_active=False, price_xof__isnull=True) if enabled else [],
        "current": current, "active_plan": services.active_plan(request.user) if enabled else None,
        "pending": pending, "pending_payment": pending_payment, "renewal_payment": renewal_payment,
        "promoted_ids": promoted_property_ids_for_owner(request.user) if enabled else set(),
        "payments": SubscriptionPayment.objects.filter(owner=request.user).select_related("plan")[:20],
        "trial_days": services.settings.SUBSCRIPTION_TRIAL_DAYS,
        "dash_role": "owner", "active": "subscription",
    })


@role_required(User.Role.OWNER)
@require_POST
def subscription_action(request):
    action = request.POST.get("action")
    try:
        if action == "subscribe":
            sub, payment = services.subscribe(request.user, request.POST.get("plan", ""))
            if payment:
                return redirect("dashboard:owner_subscription_payment", reference=payment.reference)
            messages.success(request, f"Plan actuel : {sub.plan.name}" + (f" — {sub.get_status_display()}" if sub.status != "active" else "")
                             + (f". Passage à {sub.scheduled_plan.name} programmé à l'échéance." if sub.scheduled_plan else "."))
        elif action == "renew":
            payment = services.request_renewal(request.user)
            return redirect("dashboard:owner_subscription_payment", reference=payment.reference)
        elif action == "cancel":
            services.cancel(request.user)
            messages.success(request, "Renouvellement désactivé. Vos avantages restent actifs jusqu'à l'échéance.")
        else:
            raise services.SubscriptionError("Action inconnue.")
    except services.SubscriptionError as exc:
        messages.error(request, str(exc))
    return redirect("dashboard:owner_subscription")


def _own_payment(request, reference):
    if not services.subscriptions_enabled():
        raise Http404
    return get_object_or_404(SubscriptionPayment.objects.select_related("plan", "subscription"),
                             reference=reference, owner=request.user)


@role_required(User.Role.OWNER)
def subscription_payment(request, reference):
    payment = _own_payment(request, reference)
    if request.method == "POST":
        try:
            payment = services.decide_payment(request.user, payment.reference, request.POST.get("outcome", ""))
        except services.SubscriptionError as exc:
            messages.error(request, str(exc))
            return redirect("dashboard:owner_subscription_payment", reference=reference)
        if payment.status == SubscriptionPayment.Status.SUCCEEDED:
            messages.success(request, "Paiement simulé réussi : abonnement activé (aucun argent réel).")
        elif payment.status == SubscriptionPayment.Status.PENDING:
            messages.info(request, "Paiement simulé en attente.")
            return redirect("dashboard:owner_subscription_payment", reference=reference)
        else:
            messages.warning(request, f"Paiement simulé : {payment.get_status_display()}. Aucun avantage accordé.")
        return redirect("dashboard:owner_subscription")
    return render(request, "owner_subscriptions/payment.html", {
        "payment": payment, "choices": SIM_CHOICES, "dash_role": "owner", "active": "subscription"})
