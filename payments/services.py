"""
Logique métier des paiements de mise en relation.

Toutes les transitions d'état sont décidées ici, côté serveur, à partir de l'état
fourni par le fournisseur (FedaPay ou simulation). Les paramètres d'URL et les
pages de retour ne confirment jamais un paiement.
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import PaymentAttempt, PaymentEvent
from .providers import STATUS_MAP, ProviderError, get_provider
from .relations import grant_owner_relation, has_owner_relation

logger = logging.getLogger(__name__)


class PaymentNotAllowed(Exception):
    """Le paiement ne peut pas être initié (relation déjà existante, rôle invalide...)."""


def simulation_enabled():
    return settings.PAYMENT_MODE == PaymentAttempt.Provider.SIMULATION


def demo_isolation_required():
    return simulation_enabled() and settings.PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY


def demo_pair_allowed(client, owner):
    """En démonstration isolée, seuls des comptes de démonstration peuvent être mis en relation."""
    return not demo_isolation_required() or bool(client and owner and client.is_demo and owner.is_demo)


def _expiry_threshold():
    return timezone.now() - timedelta(minutes=settings.PAYMENT_ATTEMPT_TTL_MINUTES)


def start_contact_payment(request, client, property_obj):
    """
    Initie (ou reprend) une tentative de paiement pour entrer en relation avec le
    propriétaire du bien. Retourne (attempt, redirect_url).
    """
    owner = property_obj.owner
    if client.role != client.Role.CLIENT:
        raise PaymentNotAllowed("Seul un compte client peut payer une mise en relation.")
    if owner is None or owner == client:
        raise PaymentNotAllowed("Ce bien n'a pas de propriétaire contactable.")
    if has_owner_relation(client, owner):
        raise PaymentNotAllowed("Vous êtes déjà en relation avec ce propriétaire.")
    if not demo_pair_allowed(client, owner):
        raise PaymentNotAllowed(
            "Mode démonstration : la mise en relation simulée est réservée aux comptes et annonces de démonstration."
        )

    provider = get_provider()
    # Reprise : une tentative encore valide pour ce propriétaire est réutilisée (pas de double paiement).
    attempt = (
        PaymentAttempt.objects.filter(
            client=client, owner=owner, provider=provider.name,
            status=PaymentAttempt.Status.PENDING, created_at__gte=_expiry_threshold(),
        ).order_by("-created_at").first()
    )
    if attempt is None:
        attempt = PaymentAttempt.objects.create(
            client=client, owner=owner, property=property_obj, provider=provider.name,
            amount=settings.CONTACT_FEE_AMOUNT, currency=settings.CONTACT_FEE_CURRENCY,
        )
    url = provider.start(request, attempt)
    logger.info("Paiement %s initié (%s) client=%s owner=%s", attempt.reference, provider.name, client.pk, owner.pk)
    return attempt, url


def _record_event(attempt, event_key, source, reported_status, note=""):
    """Enregistre l'événement ; retourne None si la même clé a déjà été traitée (idempotence)."""
    try:
        with transaction.atomic():
            return PaymentEvent.objects.create(
                attempt=attempt, event_key=event_key[:150], source=source,
                reported_status=(reported_status or "")[:30], status_before=attempt.status, note=note[:255],
            )
    except IntegrityError:
        logger.info("Événement de paiement déjà traité : %s", event_key)
        return None


def _on_approved(attempt):
    """Crée la relation (une seule par propriétaire) et les notifications associées."""
    from messaging.models import Conversation, Message
    from notifications.models import Notification

    from accounts.models import User

    if attempt.property is None:
        return
    # Verrou sur le client : deux confirmations concurrentes (tentatives différentes pour le
    # même propriétaire) ne peuvent pas créer deux relations (effectif sur PostgreSQL).
    User.objects.select_for_update().filter(pk=attempt.client_id).first()
    unlock, created = grant_owner_relation(attempt.client, attempt.property)
    attempt.relation_granted = True
    if not created:
        return
    conversation, conv_created = Conversation.objects.get_or_create(
        buyer=attempt.client, owner=attempt.owner, property=attempt.property,
    )
    if conv_created:
        Message.objects.create(
            conversation=conversation, sender=attempt.client,
            body=f"Bonjour, je suis intéressé par votre bien « {attempt.property.title} ». J'aimerais avoir plus d'informations.",
        )
    Notification.objects.create(
        user=attempt.owner,
        title="Nouvelle mise en relation",
        message=f"{attempt.client.get_full_name() or attempt.client.username} est désormais en relation avec vous.",
        notification_type="systeme",
        link=f"/dashboard/proprietaire/messagerie/{conversation.pk}/",
    )


def apply_provider_status(attempt_id, provider_status, source, event_key, note=""):
    """
    Applique un statut fourni par le fournisseur (déjà vérifié côté serveur).
    Idempotent : une clé d'événement déjà vue est ignorée ; un état terminal ne change plus.
    Retourne la tentative à jour.
    """
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().select_related("client", "owner", "property").get(pk=attempt_id)
        event = _record_event(attempt, event_key, source, provider_status, note)
        if event is None or attempt.is_terminal:
            if event is not None:
                event.status_after = attempt.status
                event.save(update_fields=["status_after"])
            return attempt

        new_status = STATUS_MAP.get((provider_status or "").lower(), PaymentAttempt.Status.PENDING)
        if new_status == PaymentAttempt.Status.PENDING and attempt.created_at < _expiry_threshold():
            new_status = PaymentAttempt.Status.EXPIRED
        if (new_status == PaymentAttempt.Status.APPROVED and attempt.is_simulation
                and not demo_pair_allowed(attempt.client, attempt.owner)):
            # Défense en profondeur : une simulation ne donne jamais de droits à des comptes réels.
            new_status = PaymentAttempt.Status.FAILED
            event.note = "Simulation refusée : comptes hors démonstration"
        attempt.status = new_status
        attempt.last_error = ""
        if new_status == PaymentAttempt.Status.APPROVED:
            attempt.confirmed_at = timezone.now()
            _on_approved(attempt)
        attempt.save()
        event.status_after = attempt.status
        event.save(update_fields=["status_after", "note"])
        logger.info("Paiement %s : %s → %s (%s)", attempt.reference, event.status_before, attempt.status, source)
        return attempt


def verify_attempt(attempt, source=PaymentEvent.Source.RETURN):
    """
    Interroge le fournisseur côté serveur et applique le résultat.
    En cas d'erreur technique ou de délai dépassé, le statut ne change pas et l'erreur est
    conservée pour l'affichage ; l'utilisateur peut relancer la vérification.
    """
    if attempt.is_terminal:
        return attempt
    if attempt.is_simulation != simulation_enabled():
        # - tentative simulée hors mode démonstration : jamais confirmée ;
        # - tentative FedaPay en mode démonstration : aucun appel à l'API réelle.
        return attempt
    provider = get_provider(attempt.provider)
    try:
        provider_status = provider.fetch_status(attempt)
    except ProviderError as exc:
        PaymentAttempt.objects.filter(pk=attempt.pk).update(last_error=str(exc)[:255])
        attempt.refresh_from_db()
        logger.warning("Vérification du paiement %s impossible : %s", attempt.reference, exc)
        return attempt
    key = f"{source}:{attempt.reference}:{provider_status}:{uuid.uuid4().hex}"
    return apply_provider_status(attempt.pk, provider_status, source, key)
