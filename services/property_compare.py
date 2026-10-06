"""
Comparaison intelligente de biens DOMIORA.

- Les faits proviennent uniquement de la base (données publiques de l'annonce).
- Les avantages / inconvénients sont calculés de façon déterministe.
- Le LLM (optionnel) rédige seulement une synthèse à partir de ces faits ;
  une synthèse citant un nombre absent des faits est rejetée.
"""
import json
import logging
import re

from services.property_search import display_city, normalize

logger = logging.getLogger(__name__)

MISSING = "Information non renseignée"
LOCAL_CURRENCIES = {"fcfa", "xof", "cfa", "f cfa", ""}


def _is_local(prop):
    return normalize(prop.currency) in LOCAL_CURRENCIES


def _money(value):
    return f"{int(round(value)):,}".replace(",", " ") + " FCFA"


def build_facts(prop):
    """Fiche de faits publics d'un bien ; les valeurs absentes sont explicites."""
    surface = float(prop.surface_area or 0)
    price = float(prop.price)
    amenities = sorted(a.name for a in prop.amenities.all())
    residential = prop.property_type not in ("terrain", "commercial")
    price_per_m2 = _money(price / surface) + " / m²" if surface > 1 and _is_local(prop) else MISSING
    return {
        "id": prop.pk,
        "title": prop.title,
        "url": prop.get_absolute_url(),
        "image": prop.primary_image,
        "rows": [
            ("Prix", prop.price_display),
            ("Transaction", prop.get_transaction_type_display()),
            ("Type", prop.get_property_type_display()),
            ("Ville", display_city(prop.city) or MISSING),
            ("Quartier", prop.neighborhood or MISSING),
            ("Chambres", str(prop.bedrooms) if prop.bedrooms else (MISSING if residential else "—")),
            ("Salles de bain", str(prop.bathrooms) if prop.bathrooms else (MISSING if residential else "—")),
            ("Superficie", f"{surface:.0f} m²" if surface > 1 else MISSING),
            ("Prix au m²", price_per_m2),
            ("Année de construction", str(prop.year_built) if prop.year_built else MISSING),
            ("Disponibilité", prop.get_status_display()),
            ("Propriétaire vérifié", "Oui" if prop.owner_verified else "Non"),
            ("Équipements", ", ".join(amenities) if amenities else MISSING),
        ],
        "_price": price,
        "_surface": surface,
        "_amenities": set(amenities),
    }


def build_insights(facts_list, properties):
    """Avantages / inconvénients déterministes, uniquement sur données présentes."""
    insights = {f["id"]: {"pros": [], "cons": []} for f in facts_list}
    notes = []
    by_id = {p.pk: p for p in properties}

    transactions = {by_id[f["id"]].transaction_type for f in facts_list}
    comparable_price = [f for f in facts_list if _is_local(by_id[f["id"]])]
    if len(transactions) > 1:
        notes.append("Ces biens mélangent vente et location : leurs prix ne sont pas directement comparables.")
    elif len(comparable_price) >= 2:
        cheapest = min(comparable_price, key=lambda f: f["_price"])
        priciest = max(comparable_price, key=lambda f: f["_price"])
        if cheapest["_price"] != priciest["_price"]:
            insights[cheapest["id"]]["pros"].append("Le prix le plus bas de la sélection")
            insights[priciest["id"]]["cons"].append("Le prix le plus élevé de la sélection")

    with_beds = [f for f in facts_list if by_id[f["id"]].bedrooms]
    if len(with_beds) >= 2:
        top = max(with_beds, key=lambda f: by_id[f["id"]].bedrooms)
        if sum(1 for f in with_beds if by_id[f["id"]].bedrooms == by_id[top["id"]].bedrooms) == 1:
            insights[top["id"]]["pros"].append(f"Le plus de chambres ({by_id[top['id']].bedrooms})")

    with_surface = [f for f in facts_list if f["_surface"] > 1]
    if len(with_surface) >= 2:
        largest = max(with_surface, key=lambda f: f["_surface"])
        insights[largest["id"]]["pros"].append(f"La plus grande superficie ({largest['_surface']:.0f} m²)")
        priced = [f for f in with_surface if _is_local(by_id[f["id"]])]
        if len(priced) >= 2 and len(transactions) == 1:
            best = min(priced, key=lambda f: f["_price"] / f["_surface"])
            insights[best["id"]]["pros"].append("Le meilleur prix au m²")

    for f in facts_list:
        others = set().union(*(o["_amenities"] for o in facts_list if o["id"] != f["id"])) if len(facts_list) > 1 else set()
        unique = sorted(f["_amenities"] - others)
        if unique:
            insights[f["id"]]["pros"].append("Seul à proposer : " + ", ".join(unique[:4]))
        if by_id[f["id"]].owner_verified:
            insights[f["id"]]["pros"].append("Propriétaire vérifié")
        missing = [label for label, value in f["rows"] if value == MISSING and label != "Prix au m²"]
        if missing:
            insights[f["id"]]["cons"].append("Non renseigné : " + ", ".join(missing).lower())
    return insights, notes


def _fallback_summary(facts_list, insights, notes):
    parts = []
    for f in facts_list:
        pros = insights[f["id"]]["pros"]
        if pros:
            parts.append(f"« {f['title']} » : {pros[0].lower()}.")
    parts.extend(notes)
    if not parts:
        return "Ces biens présentent des caractéristiques proches. Consultez le tableau ci-dessous pour le détail."
    return " ".join(parts)


def _numbers(text):
    return {re.sub(r"\D", "", n) for n in re.findall(r"\d[\d\s  ]*\d|\d", text)}


def _llm_summary(facts_list, insights, notes):
    from services import llm

    if not llm.is_configured():
        return None
    public = [
        {"titre": f["title"], "faits": dict(f["rows"]), "avantages": insights[f["id"]]["pros"], "inconvenients": insights[f["id"]]["cons"]}
        for f in facts_list
    ]
    system = (
        "Tu es l'assistant de comparaison immobilière de DOMIORA. Rédige en français une synthèse neutre "
        "(4 à 6 phrases) comparant les biens fournis. Utilise EXCLUSIVEMENT les faits donnés. "
        "N'invente aucune caractéristique, aucun chiffre, aucun équipement. Si une information vaut "
        f"« {MISSING} », dis-le plutôt que de supposer. Termine en indiquant quel bien convient selon "
        "la priorité (budget, espace, équipements), sans affirmer qu'un bien est disponible pour une visite. "
        'Réponds en JSON : {"summary": "..."}'
    )
    data, _ = llm.complete_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"biens": public, "remarques": notes}, ensure_ascii=False)},
        ],
        max_tokens=500,
        temperature=0.2,
    )
    summary = (data or {}).get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None
    summary = summary.strip()[:1500]
    # Garde-fou : tout nombre cité doit exister dans les faits.
    allowed = _numbers(json.dumps(public, ensure_ascii=False)) | {str(i) for i in range(0, 11)}
    if not _numbers(summary) <= allowed:
        logger.warning("Comparison summary rejected: unknown numbers %s", _numbers(summary) - allowed)
        return None
    return summary


def compare(properties, use_llm=True):
    """Retourne la comparaison sérialisable des biens fournis (déjà filtrés par visibilité)."""
    facts_list = [build_facts(p) for p in properties]
    insights, notes = build_insights(facts_list, properties)
    summary, source = None, "local"
    if use_llm and len(facts_list) >= 2:
        try:
            summary = _llm_summary(facts_list, insights, notes)
        except Exception:
            logger.exception("Comparison summary failed")
        if summary:
            source = "ai"
    if not summary:
        summary = _fallback_summary(facts_list, insights, notes)
    return {
        "summary": summary,
        "source": source,
        "notes": notes,
        "properties": [
            {
                "id": f["id"],
                "title": f["title"],
                "url": f["url"],
                "image": f["image"],
                "rows": [{"label": label, "value": value} for label, value in f["rows"]],
                "pros": insights[f["id"]]["pros"],
                "cons": insights[f["id"]]["cons"],
            }
            for f in facts_list
        ],
    }
