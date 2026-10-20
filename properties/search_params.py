"""Lecture tolérante des paramètres numériques de recherche (site et API)."""
import re
from decimal import Decimal, InvalidOperation

_SPACES = re.compile(r"[\s  ]")
_THOUSANDS_DOT = re.compile(r"\d{1,3}(\.\d{3})+")
_PLAIN = re.compile(r"\d{1,15}(\.\d{1,2})?")


def parse_number(raw, integer=False):
    """
    « 10000 », « 10 000 », « 10.000 » → 10000 ; « 12,5 » → 12.5 (sauf integer=True).
    Valeur vide, négative ou illisible → None : le filtre est ignoré au lieu de provoquer une erreur.
    Aucune borne : tout montant présent en base peut être recherché.
    """
    text = _SPACES.sub("", str(raw or "")).replace("FCFA", "").replace("fcfa", "")
    if not text:
        return None
    if _THOUSANDS_DOT.fullmatch(text):
        text = text.replace(".", "")
    text = text.replace(",", ".")
    if not _PLAIN.fullmatch(text):  # refuse notation scientifique, signes, texte
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if value < 0 or not value.is_finite():
        return None
    if integer:
        return int(value) if value == value.to_integral_value() else None
    return value


def apply_numeric_filters(qs, params):
    """Applique prix min/max, chambres, salles de bain et surface minimales depuis un QueryDict."""
    lookups = (
        ("price_min", "price__gte", False), ("price_max", "price__lte", False),
        ("bedrooms", "bedrooms__gte", True), ("bathrooms", "bathrooms__gte", True),
        ("surface_min", "surface_area__gte", False),
    )
    for param, lookup, integer in lookups:
        value = parse_number(params.get(param), integer=integer)
        if value is not None:
            qs = qs.filter(**{lookup: value})
    return qs
