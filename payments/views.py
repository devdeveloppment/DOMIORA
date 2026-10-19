import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from properties.fedapay import verify_fedapay_webhook_signature

from .models import PaymentAttempt, PaymentEvent
from .providers import ProviderError, SimulationProvider
from .services import _record_event, apply_provider_status, simulation_enabled, verify_attempt

logger = logging.getLogger(__name__)

SIMULATOR_CHOICES = [
    ("approved", "Paiement réussi", "Le fournisseur confirme le paiement."),
    ("declined", "Paiement refusé", "Solde insuffisant ou refus de l'opérateur."),
    ("canceled", "Paiement annulé", "Le client abandonne sur la page de paiement."),
    ("pending", "Paiement en attente", "Le fournisseur n'a pas encore tranché."),
    ("timeout", "Délai dépassé", "Le fournisseur ne répond pas à temps."),
    ("error", "Erreur technique", "Le fournisseur renvoie une erreur."),
    ("approved_duplicate", "Réussi + notification en double", "La confirmation est envoyée deux fois."),
    ("abandon", "Retour incomplet", "Le client ferme la page sans revenir sur DOMIORA."),
]


def _own_attempt(request, reference):
    return get_object_or_404(
        PaymentAttempt.objects.select_related("property", "owner"), reference=reference, client=request.user
    )


def _simulated_notification(attempt):
    """Simule la notification serveur-à-serveur du fournisseur (clé d'idempotence stable)."""
    try:
        provider_status = SimulationProvider().fetch_status(attempt)
    except ProviderError:
        return attempt
    key = f"simulator-notify:{attempt.reference}:{provider_status}"
    return apply_provider_status(attempt.pk, provider_status, PaymentEvent.Source.SIMULATOR, key)


@login_required
def simulator(request, reference):
    if not simulation_enabled():
        raise Http404
    attempt = _own_attempt(request, reference)
    if attempt.provider != PaymentAttempt.Provider.SIMULATION:
        raise Http404
    return render(request, "payments/simulator.html", {"attempt": attempt, "choices": SIMULATOR_CHOICES})


@login_required
@require_POST
def simulator_decide(request, reference):
    if not simulation_enabled():
        raise Http404
    attempt = _own_attempt(request, reference)
    if attempt.provider != PaymentAttempt.Provider.SIMULATION:
        raise Http404
    choice = request.POST.get("outcome", "")
    valid = {c[0] for c in SIMULATOR_CHOICES}
    if choice not in valid:
        messages.error(request, "Scénario de démonstration inconnu.")
        return redirect("payments:simulator", reference=reference)
    if attempt.is_terminal:
        return redirect("payments:return", reference=reference)

    outcome = {"approved_duplicate": "approved", "abandon": "approved"}.get(choice, choice)
    PaymentAttempt.objects.filter(pk=attempt.pk).update(simulated_outcome=outcome)
    attempt.refresh_from_db()

    if choice in ("approved", "approved_duplicate", "abandon", "declined", "canceled"):
        attempt = _simulated_notification(attempt)
    if choice == "approved_duplicate":
        attempt = _simulated_notification(attempt)  # deuxième réception : ignorée
    if choice == "abandon":
        # Le client ne revient pas : la notification serveur suffit, il retrouvera son accès.
        return redirect("dashboard:client_unlocked")
    return redirect("payments:return", reference=reference)


@login_required
def payment_return(request, reference):
    """
    Page de retour : n'utilise AUCUN paramètre d'URL pour décider du statut.
    Le statut est obtenu auprès du fournisseur côté serveur.
    """
    attempt = _own_attempt(request, reference)
    attempt = verify_attempt(attempt, source=PaymentEvent.Source.RETURN)
    if attempt.status == PaymentAttempt.Status.APPROVED:
        request.session["dash_role"] = "client"
        messages.success(request, "Paiement confirmé. Vous êtes maintenant en relation avec ce propriétaire.")
        return redirect("dashboard:client_unlocked")
    return render(request, "payments/status.html", {"attempt": attempt})


@login_required
@require_POST
def payment_recheck(request, reference):
    """Reprise : relance la vérification serveur d'une tentative non terminée."""
    attempt = _own_attempt(request, reference)
    return redirect("payments:return", reference=attempt.reference)


@login_required
def my_payments(request):
    attempts = PaymentAttempt.objects.filter(client=request.user).select_related("property", "owner")[:50]
    return render(request, "payments/history.html", {"attempts": attempts, "dash_role": "client", "active": "payments"})


@csrf_exempt
@require_POST
def fedapay_webhook(request):
    """Notification FedaPay : signature vérifiée, puis statut re-vérifié auprès de l'API."""
    payload_raw = request.body.decode("utf-8", errors="replace")
    signature = request.META.get("HTTP_X_FEDAPAY_SIGNATURE", "")
    if not verify_fedapay_webhook_signature(payload_raw, signature):
        logger.warning("Webhook FedaPay rejeté : signature invalide")
        return HttpResponse(status=403)
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return HttpResponse(status=400)
    entity = payload.get("entity") or (payload.get("data") or {}).get("transaction") or {}
    trx_id = str(entity.get("id") or "")
    attempt = PaymentAttempt.objects.filter(provider=PaymentAttempt.Provider.FEDAPAY, provider_transaction_id=trx_id).first() if trx_id else None
    if attempt is None:
        logger.info("Webhook FedaPay pour une transaction inconnue")
        return HttpResponse("ignored", status=200)
    event_id = payload.get("id") or f"{trx_id}:{entity.get('status', '')}"
    if _record_event(attempt, f"webhook:fedapay:{event_id}", PaymentEvent.Source.WEBHOOK, entity.get("status", "")) is None:
        return HttpResponse("duplicate", status=200)
    verify_attempt(attempt, source=PaymentEvent.Source.WEBHOOK)
    return HttpResponse("OK", status=200)
