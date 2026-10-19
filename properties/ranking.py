"""
Classement et mise en avant des annonces (côté serveur, configurable, explicable).

Score organique « Recommandés » (0–100 environ), calculé uniquement sur les annonces
déjà filtrées par la recherche (la pertinence = respect des filtres et du texte saisi) :
  - fraîcheur  : RANKING_WEIGHTS["freshness"] × (1 − âge / RANKING_FRESHNESS_DAYS)
  - qualité    : RANKING_WEIGHTS["quality"] × complétude (photos, description, surface, coordonnées)
  - vérifié    : RANKING_WEIGHTS["verified"] si le propriétaire est vérifié
  - abonnement : niveau du plan × RANKING_WEIGHTS["plan_per_level"], plafonné à
                 RANKING_PLAN_BONUS_CAP → un abonnement ne peut pas faire passer une annonce
                 incomplète et ancienne devant toutes les autres.

Emplacements « Sponsorisé » : au plus RANKING_SPONSORED_SLOTS annonces en tête de la
première page, choisies parmi les résultats de LA recherche courante (donc pertinentes),
promues par un plan actif, avec une rotation quotidienne pondérée par le niveau du plan.
Elles restent aussi présentes dans les résultats organiques ; elles sont signalées.

Éligibilité à la promotion : annonce publiée et validée, propriétaire actif et vérifié,
abonnement en cours (essai/actif, non échu), annonce faisant partie des
max_promoted_listings meilleures annonces du propriétaire, et moins de
RANKING_MAX_OPEN_REPORTS signalements ouverts.
Aucune diffusion externe (réseaux sociaux, Google…) n'est effectuée.
"""
import hashlib
import random

from django.conf import settings
from django.utils import timezone

RANKING_MAX_OPEN_REPORTS = 2


def _weights():
    return settings.RANKING_WEIGHTS


def quality_ratio(prop):
    images = len(prop.images.all())  # utilise le prefetch
    parts = [
        0.4 * min(images, 5) / 5,
        0.3 if len(prop.description or "") >= 200 else 0.15 if prop.description else 0,
        0.15 if prop.surface_area else 0,
        0.15 if prop.latitude and prop.longitude else 0,
    ]
    return sum(parts)


def plan_levels_for(owner_ids, now=None):
    """{owner_id: (visibility_level, max_promoted_listings)} pour les abonnements en cours."""
    from owner_subscriptions.models import OwnerSubscription
    from owner_subscriptions.services import subscriptions_enabled

    if not subscriptions_enabled() or not owner_ids:
        return {}
    now = now or timezone.now()
    rows = (OwnerSubscription.objects.filter(owner_id__in=set(owner_ids), status__in=OwnerSubscription.CURRENT,
                                             plan__visibility_level__gt=0)
            .exclude(current_period_end__lte=now)
            .values_list("owner_id", "plan__visibility_level", "plan__max_promoted_listings"))
    return {o: (lvl, mx) for o, lvl, mx in rows}


def score(prop, level=0, now=None):
    now = now or timezone.now()
    w = _weights()
    age_days = max((now - prop.created_at).total_seconds() / 86400, 0)
    freshness = w["freshness"] * max(0.0, 1 - age_days / settings.RANKING_FRESHNESS_DAYS)
    quality = w["quality"] * quality_ratio(prop)
    verified = w["verified"] if prop.owner and prop.owner.verification_status == "approved" else 0
    bonus = min(level * w["plan_per_level"], settings.RANKING_PLAN_BONUS_CAP)
    return round(freshness + quality + verified + bonus, 2)


def _eligible_owner(prop):
    owner = prop.owner
    return bool(owner and owner.is_active and owner.verification_status == "approved")


def _open_reports(prop_ids):
    from moderation.models import ListingReport

    counts = {}
    for pid in ListingReport.objects.filter(property_id__in=prop_ids,
                                            status__in=["open", "reviewing"]).values_list("property_id", flat=True):
        counts[pid] = counts.get(pid, 0) + 1
    return counts


def promoted_property_ids_for_owner(owner, now=None):
    """Annonces de ce propriétaire actuellement éligibles à la mise en avant."""
    from properties.models import Property

    levels = plan_levels_for([owner.pk], now)
    if owner.pk not in levels or owner.verification_status != "approved":
        return set()
    _, max_n = levels[owner.pk]
    props = list(Property.objects.filter(owner=owner, is_published=True, is_validated=True)
                 .select_related("owner").prefetch_related("images"))
    reports = _open_reports([p.pk for p in props])
    props = [p for p in props if reports.get(p.pk, 0) < RANKING_MAX_OPEN_REPORTS]
    props.sort(key=lambda p: (quality_ratio(p), p.created_at), reverse=True)
    return {p.pk for p in props[:max_n]}


def rank(properties, now=None, levels=None):
    """Trie une liste d'annonces par score décroissant ; annote .rank_score et .plan_level."""
    now = now or timezone.now()
    items = list(properties)
    levels = plan_levels_for([p.owner_id for p in items], now) if levels is None else levels
    for p in items:
        lvl = levels.get(p.owner_id, (0, 0))[0] if _eligible_owner(p) else 0
        p.plan_level = lvl
        p.rank_score = score(p, lvl, now)
    items.sort(key=lambda p: (p.rank_score, p.created_at), reverse=True)
    return items


def sponsored(properties, now=None, slots=None, levels=None):
    """Sélectionne les annonces « Sponsorisé » parmi les résultats fournis (déjà filtrés)."""
    now = now or timezone.now()
    slots = settings.RANKING_SPONSORED_SLOTS if slots is None else slots
    items = list(properties)
    levels = plan_levels_for([p.owner_id for p in items], now) if levels is None else levels
    if not levels or slots <= 0:
        return []
    by_owner = {}
    for p in items:
        if p.owner_id in levels and _eligible_owner(p):
            by_owner.setdefault(p.owner_id, []).append(p)
    reports = _open_reports([p.pk for ps in by_owner.values() for p in ps])
    candidates = []
    for owner_id, props in by_owner.items():
        level, max_n = levels[owner_id]
        props = [p for p in props if reports.get(p.pk, 0) < RANKING_MAX_OPEN_REPORTS]
        props.sort(key=lambda p: (quality_ratio(p), p.created_at), reverse=True)
        candidates += [(p, level) for p in props[:max_n]]
    day = now.date().isoformat()

    def key(entry):
        prop, level = entry
        seed = int(hashlib.sha256(f"{day}:{prop.pk}".encode()).hexdigest()[:12], 16)
        return random.Random(seed).random() ** (1 / level)  # tirage pondéré par le niveau, stable sur la journée

    chosen = sorted(candidates, key=key, reverse=True)[:slots]
    for prop, level in chosen:
        prop.is_sponsored = True
        prop.plan_level = level
    return [p for p, _ in chosen]
