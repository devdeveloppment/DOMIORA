"""
Dons volontaires : montant libre, confirmation uniquement par vérification serveur.

- Simulation (PAYMENT_MODE=simulation) : interface de démonstration, aucun appel réseau, don marqué test.
- FedaPay : transaction créée via l'API ; le statut est toujours relu auprès de l'API FedaPay
  (retour navigateur ou webhook), jamais déduit des paramètres reçus. En sandbox, le don est marqué test.
- Idempotence : chaque notification a une clé unique (DonationEvent) ; un état final ne change plus.
"""
import logging
import re
import uuid

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from payments.services import is_test_payment

from .models import Donation, DonationEvent

logger = logging.getLogger(__name__)

# Seule borne basse : la contrainte du prestataire (FedaPay refuse les montants trop faibles) ;
# configurable, aucune autre limite métier. Borne haute = capacité du champ en base.
MAX_STORABLE_AMOUNT = 2_147_483_647
# Statuts FedaPay → statuts du don (mêmes correspondances que les frais de mise en relation).
STATUS_MAP = {
    "approved": Donation.Status.APPROVED, "transferred": Donation.Status.APPROVED,
    "declined": Donation.Status.DECLINED, "canceled": Donation.Status.CANCELED,
    "cancelled": Donation.Status.CANCELED, "refunded": Donation.Status.CANCELED,
    "pending": Donation.Status.PENDING, "created": Donation.Status.PENDING,
}


class DonationError(Exception):
    pass


def min_amount():
    return int(getattr(settings, "DONATION_MIN_AMOUNT", 100))


def parse_amount(raw):
    """Accepte « 1000 », « 1 000 », « 1.000 » ; refuse décimales, négatifs, texte et montants hors bornes."""
    text = re.sub(r"[\s ]", "", str(raw or ""))
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):  # « 1.000 » : point séparateur de milliers
        text = text.replace(".", "")
    if not text.isdigit():
        raise DonationError("Saisissez un montant entier en FCFA (par exemple 500).")
    amount = int(text)
    if amount < min_amount():
        raise DonationError(f"Le prestataire de paiement n'accepte pas les montants inférieurs à {min_amount()} FCFA.")
    if amount > MAX_STORABLE_AMOUNT:
        raise DonationError("Montant trop élevé.")
    return amount


def start_donation(request, amount, email="", phone=""):
    """Crée le don en attente et retourne (don, URL de paiement)."""
    provider = Donation.Provider.SIMULATION if settings.PAYMENT_MODE == "simulation" else Donation.Provider.FEDAPAY
    user = request.user if request.user.is_authenticated else None
    donation = Donation.objects.create(
        donor=user, donor_email=(email or getattr(user, "email", "") or "")[:254], donor_phone=(phone or "")[:30],
        amount=amount, currency=getattr(settings, "CONTACT_FEE_CURRENCY", "XOF"), provider=provider,
        is_test=is_test_payment(provider),
    )
    if provider == Donation.Provider.SIMULATION:
        donation.provider_transaction_id = f"SIM-DON-{donation.reference.hex[:10].upper()}"
        donation.save(update_fields=["provider_transaction_id", "updated_at"])
        return donation, reverse("core:donation_simulator", args=[donation.reference])
    return donation, _fedapay_start(request, donation)


def _fedapay_headers():
    from properties.fedapay import _get_fedapay_secret_key

    secret = _get_fedapay_secret_key()
    if not secret:
        raise DonationError("Le paiement en ligne n'est pas configuré.")
    return {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}


def _fedapay_start(request, donation):
    from properties.fedapay import _get_fedapay_base_url

    payload = {
        "description": "Don à DOMIORA",
        "amount": donation.amount,
        "currency": {"iso": donation.currency},
        "callback_url": request.build_absolute_uri(reverse("core:donation_return", args=[donation.reference])),
        "customer": {"firstname": "Donateur", "lastname": "", "email": donation.donor_email},
        "custom_metadata": {"donation_reference": str(donation.reference)},
    }
    base = _get_fedapay_base_url()
    try:
        resp = requests.post(f"{base}/transactions", json=payload, headers=_fedapay_headers(), timeout=20)
        resp.raise_for_status()
        trx = (resp.json().get("v1/transaction") or resp.json().get("transaction") or {})
        if not trx.get("id"):
            raise DonationError("Réponse du prestataire incomplète.")
        donation.provider_transaction_id = str(trx["id"])
        donation.save(update_fields=["provider_transaction_id", "updated_at"])
        token = requests.post(f"{base}/transactions/{trx['id']}/token", headers=_fedapay_headers(), timeout=20).json()
    except requests.RequestException as error:
        _fail(donation, "Erreur de communication avec le prestataire")
        raise DonationError("Le prestataire de paiement ne répond pas. Réessayez dans quelques instants.") from error
    url = token.get("url") or (token.get("token") and
                                f"https://{'sandbox-' if getattr(settings, 'FEDAPAY_SANDBOX', True) else ''}checkout.fedapay.com/checkout/{token['token']}")
    if not url:
        _fail(donation, "URL de paiement manquante")
        raise DonationError("Le lien de paiement n'a pas pu être créé.")
    return url


def _fail(donation, error):
    Donation.objects.filter(pk=donation.pk, status=Donation.Status.PENDING).update(
        status=Donation.Status.FAILED, last_error=error[:255])


def fetch_provider_status(donation):
    """Statut lu côté serveur (décision de démonstration stockée en base, ou API FedaPay)."""
    if donation.provider == Donation.Provider.SIMULATION:
        return donation.simulated_outcome or "pending"
    from properties.fedapay import _get_fedapay_base_url

    if not donation.provider_transaction_id:
        return "pending"
    resp = requests.get(f"{_get_fedapay_base_url()}/transactions/{donation.provider_transaction_id}",
                        headers=_fedapay_headers(), timeout=15)
    resp.raise_for_status()
    trx = resp.json().get("v1/transaction") or resp.json().get("transaction") or {}
    return trx.get("status", "pending")


def apply_status(donation_id, provider_status, source, event_key):
    """Applique un statut déjà vérifié ; idempotent (clé d'événement unique, état final figé)."""
    with transaction.atomic():
        donation = Donation.objects.select_for_update().get(pk=donation_id)
        try:
            with transaction.atomic():
                event = DonationEvent.objects.create(
                    donation=donation, event_key=event_key[:150], source=source,
                    reported_status=(provider_status or "")[:30], status_before=donation.status)
        except IntegrityError:
            return donation  # notification déjà traitée
        if not donation.is_terminal:
            donation.status = STATUS_MAP.get((provider_status or "").lower(), Donation.Status.PENDING)
            if donation.status == Donation.Status.APPROVED:
                donation.confirmed_at = timezone.now()
            donation.last_error = ""
            donation.save()
        event.status_after = donation.status
        event.save(update_fields=["status_after"])
    return donation


def verify(donation, source="return"):
    """Relit le statut auprès du prestataire et l'applique. Une erreur technique ne change pas le statut."""
    if donation.is_terminal:
        return donation
    if (donation.provider == Donation.Provider.SIMULATION) != (settings.PAYMENT_MODE == "simulation"):
        return donation  # jamais de confirmation hors du mode qui a créé le don
    try:
        status = fetch_provider_status(donation)
    except (requests.RequestException, DonationError) as error:
        Donation.objects.filter(pk=donation.pk).update(last_error=(str(error) or type(error).__name__)[:255])
        donation.refresh_from_db()
        return donation
    return apply_status(donation.pk, status, source, f"{source}:{donation.reference}:{status}:{uuid.uuid4().hex}")


def handle_webhook_transaction(entity, event_id):
    """Appelé par le webhook FedaPay commun : retourne True si la transaction était un don."""
    trx_id = str(entity.get("id") or "")
    donation = Donation.objects.filter(provider=Donation.Provider.FEDAPAY, provider_transaction_id=trx_id).first() if trx_id else None
    if donation is None:
        return False
    try:
        with transaction.atomic():
            DonationEvent.objects.create(donation=donation, event_key=f"webhook:{event_id}"[:150], source="webhook",
                                         reported_status=str(entity.get("status", ""))[:30], status_before=donation.status)
    except IntegrityError:
        return True  # doublon : déjà traité
    verify(donation, source="webhook")
    return True
