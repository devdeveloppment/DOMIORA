"""
Éligibilité aux avis sur un propriétaire.

Règle : un avis « vérifié » par relation client ↔ propriétaire (unique_together owner/reviewer),
uniquement si :
1. l'auteur est un CLIENT ;
2. un paiement de mise en relation est CONFIRMÉ (PaymentAttempt approuvé, relation accordée)
   pour ce propriétaire — une simulation n'est admise qu'entre comptes de démonstration ;
3. la relation est ACHEVÉE : au moins une visite acceptée dont la date est passée.
   (Définition à valider métier ; les relations historiques sans PaymentAttempt ne sont pas
   éligibles faute de preuve de paiement.)
"""
from django.utils import timezone


def eligible_payment(reviewer, owner):
    from payments.models import PaymentAttempt

    payments = PaymentAttempt.objects.filter(client=reviewer, owner=owner, status=PaymentAttempt.Status.APPROVED,
                                             relation_granted=True).order_by("confirmed_at")
    for payment in payments:
        if payment.provider == PaymentAttempt.Provider.FEDAPAY:
            return payment
        if reviewer.is_demo and owner.is_demo:
            return payment
    return None


def relation_completed(reviewer, owner):
    from messaging.models import VisitRequest

    return VisitRequest.objects.filter(conversation__buyer=reviewer, conversation__owner=owner,
                                       status=VisitRequest.Status.ACCEPTED, proposed_date__lte=timezone.now()).exists()


def review_eligibility(reviewer, owner):
    """Retourne (paiement, motif_de_refus)."""
    if getattr(reviewer, "role", None) != "client":
        return None, "Seuls les clients peuvent laisser un avis sur un propriétaire."
    payment = eligible_payment(reviewer, owner)
    if payment is None:
        return None, "Un avis nécessite une mise en relation payée et confirmée avec ce propriétaire."
    if not relation_completed(reviewer, owner):
        return None, "Un avis est possible après une visite acceptée et effectuée."
    return payment, ""
