import hmac
import hashlib
import requests
import uuid
import logging
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

# FedaPay API base URLs
FEDAPAY_LIVE_URL = "https://api.fedapay.com/v1"
FEDAPAY_SANDBOX_URL = "https://sandbox-api.fedapay.com/v1"


def _get_fedapay_base_url():
    """Retourne l'URL de base selon le mode (sandbox ou live)."""
    if getattr(settings, 'FEDAPAY_SANDBOX', True):
        return FEDAPAY_SANDBOX_URL
    return FEDAPAY_LIVE_URL


def _get_fedapay_public_key():
    """Retourne la clé publique FedaPay (utilisée côté JS)."""
    return getattr(settings, 'FEDAPAY_PUBLIC_KEY', '')


def _get_fedapay_secret_key():
    """Retourne la clé secrète FedaPay."""
    return getattr(settings, 'FEDAPAY_SECRET_KEY', '')


def generate_fedapay_payment_url(request, property_slug, amount=500,
                                  customer_name="", customer_email="",
                                  customer_phone="", is_donation=False):
    """
    Crée une transaction FedaPay et retourne (payment_url, transaction_id).
    En cas d'erreur : (None, error_info).
    """
    secret_key = _get_fedapay_secret_key()
    if not secret_key:
        logger.error("FedaPay: FEDAPAY_SECRET_KEY non configurée dans l'environnement.")
        return None, "Configuration manquante"

    transaction_id = str(uuid.uuid4())
    request.session["pending_transaction_id"] = transaction_id
    request.session.modified = True

    if is_donation:
        callback_url = request.build_absolute_uri(reverse('core:donate_confirmation'))
        cancel_url = request.build_absolute_uri(reverse('core:donate'))
        description = "Don pour DOMIORA"
    else:
        callback_url = request.build_absolute_uri(
            reverse('properties:payment_confirmation', args=[property_slug])
        )
        cancel_url = request.build_absolute_uri(
            reverse('properties:detail', args=[property_slug])
        )
        description = f"Frais de mise en relation — bien {property_slug}"

    # Les frais de mise en relation passent par payments.providers. Ce module ne sert plus
    # qu'aux dons ; en mode démonstration aucun appel FedaPay n'est effectué.
    if getattr(settings, "PAYMENT_MODE", "fedapay") == "simulation":
        logger.info("Mode démonstration : aucun appel FedaPay (don non disponible).")
        return None, "simulation"

    # Préparer le nom du client
    parts = customer_name.split() if customer_name else []
    first_name = parts[0] if parts else "Client"
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    payload = {
        "description": description,
        "amount": amount,
        "currency": {"iso": "XOF"},
        "callback_url": callback_url,
        "cancel_url": cancel_url,
        "customer": {
            "firstname": first_name,
            "lastname": last_name,
            "email": customer_email or "",
            "phone_number": {
                "number": customer_phone or "",
                "country": "TG",
            }
        },
        "meta": {
            "transaction_id": transaction_id,
            "property_slug": property_slug,
        }
    }

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    base_url = _get_fedapay_base_url()
    try:
        # Étape 1 : Créer la transaction
        response = requests.post(
            f"{base_url}/transactions",
            json=payload,
            headers=headers,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        # La réponse peut être enveloppée sous "v1/transaction" ou "transaction"
        fedapay_transaction = data.get("v1/transaction") or data.get("transaction") or {}
        fedapay_id = fedapay_transaction.get("id")

        if not fedapay_id:
            logger.error(f"FedaPay: ID de transaction manquant dans la réponse: {data}")
            return None, data

        # Étape 2 : Générer le token de paiement
        token_response = requests.post(
            f"{base_url}/transactions/{fedapay_id}/token",
            headers=headers,
            timeout=20
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        # Selon la doc FedaPay, la réponse contient directement { "token": "...", "url": "..." }
        token = token_data.get("token")
        payment_url = token_data.get("url")

        if not token and not payment_url:
            logger.error(f"FedaPay: Token/URL manquant dans la réponse: {token_data}")
            return None, token_data

        # Si l'API n'a pas retourné l'URL, on la construit manuellement
        if not payment_url and token:
            sandbox_prefix = "sandbox-" if getattr(settings, 'FEDAPAY_SANDBOX', True) else ""
            payment_url = f"https://{sandbox_prefix}checkout.fedapay.com/checkout/{token}"

        # Stocker l'ID FedaPay en session pour la vérification lors du retour
        request.session["fedapay_transaction_id"] = fedapay_id
        request.session.modified = True

        logger.info(f"FedaPay: Transaction {fedapay_id} créée → {payment_url}")
        return payment_url, transaction_id

    except requests.exceptions.HTTPError as e:
        body = e.response.text if e.response is not None else "N/A"
        logger.error(f"FedaPay erreur HTTP: {e} — Réponse: {body}")
        return None, str(e)
    except Exception as e:
        logger.error(f"FedaPay exception inattendue: {e}")
        return None, str(e)


def verify_fedapay_payment(fedapay_transaction_id):
    """
    Vérifie le statut d'une transaction FedaPay via l'API.
    Retourne: (is_paid: bool, data: dict | None)
    """
    secret_key = _get_fedapay_secret_key()
    if not secret_key:
        logger.error("FedaPay: FEDAPAY_SECRET_KEY non configurée.")
        return False, None

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    base_url = _get_fedapay_base_url()
    try:
        response = requests.get(
            f"{base_url}/transactions/{fedapay_transaction_id}",
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        transaction = data.get("v1/transaction") or data.get("transaction") or {}
        status = transaction.get("status", "")

        # FedaPay : "approved" = paiement réussi
        if status == "approved":
            logger.info(f"FedaPay: Transaction {fedapay_transaction_id} approuvée.")
            return True, transaction

        logger.info(f"FedaPay: Transaction {fedapay_transaction_id} statut={status}")
        return False, transaction

    except Exception as e:
        logger.error(f"FedaPay vérification exception: {e}")
        return False, None


def verify_fedapay_webhook_signature(payload_raw, signature, secret_key=None):
    """
    Vérifie la signature HMAC-SHA256 d'un webhook FedaPay.
    FedaPay envoie le header 'X-FedaPay-Signature'.
    """
    if not secret_key:
        secret_key = _get_fedapay_secret_key()

    if not secret_key or not signature:
        return False

    msg = payload_raw.encode('utf-8') if isinstance(payload_raw, str) else payload_raw
    expected = hmac.new(
        secret_key.encode('utf-8'),
        msg,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def fedapay_customer(firstname="", lastname="", email=""):
    """Client FedaPay sans champ vide (une adresse e-mail vide est refusée par l'API)."""
    customer = {"firstname": (firstname or "Client").strip()[:100]}
    if (lastname or "").strip():
        customer["lastname"] = lastname.strip()[:100]
    if (email or "").strip():
        customer["email"] = email.strip()
    return customer


def describe_fedapay_error(exc):
    """
    Résumé journalisable d'une erreur FedaPay : code HTTP et message de l'API (jamais la clé).
    Ex. : « HTTP 401 : clé refusée (mode sandbox/live ou clé invalide) — {...} ».
    """
    response = getattr(exc, "response", None)
    if response is None:
        return f"{exc.__class__.__name__} : {exc}"
    hints = {401: "clé refusée (clé invalide, ou clé live utilisée en mode sandbox et inversement)",
             403: "accès refusé par FedaPay", 422: "données refusées par FedaPay"}
    body = (response.text or "")[:400].replace("\n", " ")
    return f"HTTP {response.status_code} : {hints.get(response.status_code, 'erreur FedaPay')} — {body}"
