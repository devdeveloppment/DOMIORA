"""
Source unique de vérité pour la relation client ↔ propriétaire.

La relation est liée au PROPRIÉTAIRE : un paiement validé pour n'importe quel bien d'un
propriétaire ouvre l'accès à ce propriétaire. Elle est stockée via properties.PropertyUnlock
(modèle historique conservé pour compatibilité des données existantes).
"""
from properties.models import PropertyUnlock


def has_owner_relation(client, owner):
    """True si `client` dispose d'une relation valide avec `owner`."""
    if not client or not getattr(client, "is_authenticated", False) or not owner:
        return False
    return PropertyUnlock.objects.filter(user=client, property__owner=owner).exists()


def grant_owner_relation(client, property_obj):
    """
    Crée la relation si elle n'existe pas encore pour ce propriétaire.
    Retourne (unlock, created). Ne crée jamais une deuxième relation pour le même propriétaire.
    Doit être appelée uniquement après une confirmation de paiement côté serveur.
    """
    existing = (
        PropertyUnlock.objects.filter(user=client, property__owner=property_obj.owner)
        .order_by("unlocked_at")
        .first()
    )
    if existing:
        return existing, False
    return PropertyUnlock.objects.get_or_create(user=client, property=property_obj)
