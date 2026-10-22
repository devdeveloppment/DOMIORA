"""
Fournisseurs de paiement.

- SimulationProvider : démonstration. Aucun appel réseau, aucun argent réel. L'état
  « fournisseur » est la décision prise sur l'interface de démonstration, stockée côté
  serveur (PaymentAttempt.simulated_outcome) ; jamais lue depuis l'URL ou le navigateur.
- FedaPayProvider : fournisseur réel prévu. La confirmation passe toujours par
  l'API FedaPay (vérification serveur), jamais par les paramètres de retour.
"""
import logging

import requests
from django.conf import settings
from django.urls import reverse

from properties.fedapay import _get_fedapay_base_url, _get_fedapay_secret_key, describe_fedapay_error, fedapay_customer

from .models import PaymentAttempt

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Erreur technique du fournisseur : le statut de la tentative ne change pas."""


class ProviderTimeout(ProviderError):
    """Délai dépassé lors de l'échange avec le fournisseur."""


# Statuts fournisseur → statuts DOMIORA
STATUS_MAP = {
    "approved": PaymentAttempt.Status.APPROVED,
    "transferred": PaymentAttempt.Status.APPROVED,
    "declined": PaymentAttempt.Status.DECLINED,
    "canceled": PaymentAttempt.Status.CANCELED,
    "cancelled": PaymentAttempt.Status.CANCELED,
    "refunded": PaymentAttempt.Status.CANCELED,
    "pending": PaymentAttempt.Status.PENDING,
    "created": PaymentAttempt.Status.PENDING,
}


class SimulationProvider:
    name = PaymentAttempt.Provider.SIMULATION

    def start(self, request, attempt):
        """Retourne l'URL de l'interface de démonstration (aucun appel externe)."""
        attempt.provider_transaction_id = f"SIM-{attempt.reference.hex[:12].upper()}"
        attempt.save(update_fields=["provider_transaction_id", "updated_at"])
        return reverse("payments:simulator", args=[attempt.reference])

    def fetch_status(self, attempt):
        outcome = attempt.simulated_outcome
        if outcome == PaymentAttempt.SimulatedOutcome.TIMEOUT:
            raise ProviderTimeout("Délai dépassé (simulé)")
        if outcome == PaymentAttempt.SimulatedOutcome.ERROR:
            raise ProviderError("Erreur technique (simulée)")
        return outcome or "pending"


class FedaPayProvider:
    name = PaymentAttempt.Provider.FEDAPAY

    def _headers(self):
        secret = _get_fedapay_secret_key()
        if not secret:
            logger.error("FedaPay : FEDAPAY_SECRET_KEY absente (variable d'environnement à définir sur le serveur)")
            raise ProviderError("FedaPay non configuré")
        return {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}

    def start(self, request, attempt):
        headers = self._headers()
        client = attempt.client
        callback_url = request.build_absolute_uri(reverse("payments:return", args=[attempt.reference]))
        payload = {
            "description": "Frais de mise en relation DOMIORA",
            "amount": attempt.amount,
            "currency": {"iso": attempt.currency},
            "callback_url": callback_url,
            "customer": fedapay_customer(client.first_name, client.last_name, client.email),
            "custom_metadata": {"reference": str(attempt.reference)},
        }
        base = _get_fedapay_base_url()
        try:
            resp = requests.post(f"{base}/transactions", json=payload, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            trx = data.get("v1/transaction") or data.get("transaction") or {}
            trx_id = trx.get("id")
            if not trx_id:
                raise ProviderError("Réponse FedaPay sans identifiant de transaction")
            attempt.provider_transaction_id = str(trx_id)
            attempt.save(update_fields=["provider_transaction_id", "updated_at"])
            token_resp = requests.post(f"{base}/transactions/{trx_id}/token", headers=headers, timeout=20)
            token_resp.raise_for_status()
            token_data = token_resp.json()
        except requests.Timeout as exc:
            logger.error("FedaPay : délai dépassé à la création du paiement %s", attempt.reference)
            raise ProviderTimeout("Délai dépassé avec FedaPay") from exc
        except requests.RequestException as exc:
            logger.error("FedaPay : création du paiement %s refusée — %s", attempt.reference, describe_fedapay_error(exc))
            raise ProviderError("Erreur de communication avec FedaPay") from exc
        url = token_data.get("url")
        if not url and token_data.get("token"):
            prefix = "sandbox-" if getattr(settings, "FEDAPAY_SANDBOX", True) else ""
            url = f"https://{prefix}checkout.fedapay.com/checkout/{token_data['token']}"
        if not url:
            raise ProviderError("URL de paiement FedaPay manquante")
        return url

    def fetch_status(self, attempt):
        if not attempt.provider_transaction_id:
            return "pending"
        try:
            resp = requests.get(
                f"{_get_fedapay_base_url()}/transactions/{attempt.provider_transaction_id}",
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout as exc:
            raise ProviderTimeout("Délai dépassé avec FedaPay") from exc
        except requests.RequestException as exc:
            raise ProviderError("Erreur de communication avec FedaPay") from exc
        trx = data.get("v1/transaction") or data.get("transaction") or {}
        return trx.get("status", "pending")


def get_provider(name=None):
    name = name or settings.PAYMENT_MODE
    if name == PaymentAttempt.Provider.SIMULATION:
        return SimulationProvider()
    return FedaPayProvider()
