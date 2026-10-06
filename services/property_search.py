"""
Moteur de recherche immobilière intelligente de DOMIORA.

Principe (le LLM n'est jamais une autorité sur la base) :

    message -> critères structurés (LLM si disponible, sinon règles locales)
            -> fusion avec l'état de la conversation (session)
            -> question de clarification si nécessaire
            -> requête Django sur les biens publiquement visibles uniquement
            -> calcul de pertinence explicable (✓ / △ / ✗)
            -> correspondances exactes + alternatives clairement séparées

Les biens retournés proviennent exclusivement de la base. Aucune donnée
privée du propriétaire (téléphone, email, documents) n'est lue ni renvoyée.
"""
import copy
import logging
import re
import unicodedata
from decimal import Decimal

logger = logging.getLogger(__name__)

MAX_RESULTS = 6
MAX_ALTERNATIVES = 3
MAX_CANDIDATES = 400
BUDGET_TOLERANCE = 0.25  # +25 % max pour proposer une alternative
LOCAL_CURRENCIES = {"fcfa", "xof", "cfa", "f cfa"}


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def normalize(text):
    """Minuscules, sans accents, espaces simplifiés : 'Lomé' -> 'lome'."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def _contains_word(haystack, needle):
    """Recherche d'un mot/expression normalisé avec frontières de mots."""
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None


# ---------------------------------------------------------------------------
# Vocabulaire (basé sur les PropertyType réellement présents dans le modèle)
# ---------------------------------------------------------------------------
# clé -> (libellé, mots-clés normalisés, types exacts, types proches)
PROPERTY_KINDS = {
    "maison_de_ville": ("Maison de ville", ["maison de ville"], ["maison_de_ville"], ["villa", "duplex", "bungalow"]),
    "maison": (
        "Maison",
        ["maison", "maisons", "house", "logement familial"],
        ["maison_de_ville", "villa", "bungalow", "cottage", "duplex", "triplex", "chateau"],
        ["ferme", "ranch"],
    ),
    "villa": ("Villa", ["villa", "villas"], ["villa"], ["maison_de_ville", "chateau", "duplex", "triplex"]),
    "appartement": (
        "Appartement",
        ["appartement", "appartements", "appart", "apartment", "appt"],
        ["appartement", "copropriete"],
        ["studio", "loft", "penthouse", "duplex", "triplex"],
    ),
    "studio": ("Studio", ["studio", "studios"], ["studio"], ["appartement", "loft"]),
    "duplex": ("Duplex", ["duplex"], ["duplex"], ["triplex", "villa", "appartement"]),
    "triplex": ("Triplex", ["triplex"], ["triplex"], ["duplex", "villa"]),
    "loft": ("Loft", ["loft"], ["loft"], ["appartement", "studio"]),
    "penthouse": ("Penthouse", ["penthouse"], ["penthouse"], ["appartement", "duplex"]),
    "bungalow": ("Bungalow", ["bungalow"], ["bungalow"], ["cottage", "villa", "maison_de_ville"]),
    "cottage": ("Cottage", ["cottage"], ["cottage"], ["bungalow", "maison_de_ville"]),
    "chateau": ("Château", ["chateau"], ["chateau"], ["villa"]),
    "ferme": ("Ferme", ["ferme"], ["ferme"], ["ranch"]),
    "ranch": ("Ranch", ["ranch"], ["ranch"], ["ferme"]),
    "mobile_home": ("Mobile home", ["mobile home", "mobil home"], ["mobile_home"], []),
    "copropriete": ("Copropriété", ["copropriete"], ["copropriete"], ["appartement"]),
    "terrain": ("Terrain", ["terrain", "terrains", "parcelle", "parcelles", "lot de terrain"], ["terrain"], []),
    "commercial": (
        "Local commercial",
        ["local commercial", "commercial", "boutique", "magasin", "bureau", "bureaux"],
        ["commercial"],
        [],
    ),
}
# Ordre de détection : expressions longues/spécifiques d'abord.
_KIND_DETECTION_ORDER = [
    "maison_de_ville", "mobile_home", "commercial", "copropriete", "appartement", "studio",
    "duplex", "triplex", "penthouse", "loft", "villa", "bungalow", "cottage", "chateau",
    "ferme", "ranch", "terrain", "maison",
]
NON_RESIDENTIAL_KINDS = {"terrain", "commercial"}

# clé -> (libellé, alias d'équipements (noms Amenity normalisés), mots-clés dans le message/l'annonce)
FEATURES = {
    "parking": ("Parking", ["parking", "garage"], ["parking", "garage", "stationnement"]),
    "garage": ("Garage", ["garage"], ["garage"]),
    "jardin": ("Jardin", ["jardin"], ["jardin"]),
    "piscine": ("Piscine", ["piscine"], ["piscine"]),
    "climatisation": ("Climatisation", ["climatisation"], ["climatisation", "climatise", "climatisee", "clim"]),
    "meuble": ("Meublé", ["meuble"], ["meuble", "meublee", "meubles", "meublees"]),
    "securite": ("Sécurité / gardiennage", ["securite", "cloture", "gardien"], ["securite", "securise", "securisee", "gardien", "gardiennage", "cloture", "cloturee"]),
    "forage": ("Forage / eau", ["forage", "puits"], ["forage", "puits"]),
    "terrasse": ("Terrasse / balcon", ["terrasse", "balcon", "veranda"], ["terrasse", "balcon", "veranda"]),
    "wifi": ("Wifi / internet", ["wifi"], ["wifi", "internet", "fibre"]),
    "ascenseur": ("Ascenseur", ["ascenseur"], ["ascenseur"]),
    "cuisine": ("Cuisine équipée", ["cuisine equipee"], ["cuisine equipee", "cuisine amenagee"]),
    "salle_sport": ("Salle de sport", ["salle de sport"], ["salle de sport", "gym"]),
}

# Préférences « souples » : recherchées dans le texte de l'annonce, jamais supposées.
PREFERENCES = {
    "calme": ("Quartier calme", ["calme", "tranquille", "paisible"]),
    "plage": ("Proche de la plage", ["plage", "bord de mer", "vue mer"]),
    "centre": ("Proche du centre", ["centre ville", "centre-ville", "centre"]),
    "neuf": ("Récent / neuf", ["neuf", "neuve", "recent", "recente", "nouvelle construction"]),
    "lumineux": ("Lumineux", ["lumineux", "lumineuse", "ensoleille"]),
    "spacieux": ("Spacieux", ["spacieux", "spacieuse", "grand espace"]),
    "ecole": ("Proche des écoles", ["ecole", "ecoles"]),
    "marche": ("Proche d'un marché", ["marche"]),
}

KNOWN_CITIES = [
    "lome", "kara", "sokode", "kpalime", "atakpame", "tsevie", "aneho", "dapaong", "bassar",
    "notse", "mango", "tabligbo", "vogan", "badou", "cotonou", "abidjan", "accra", "ouagadougou",
]

NUMBER_WORDS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}

QUESTIONS = {
    "kind_location": "Bien sûr. Quel type de bien recherchez-vous (appartement, maison, villa, terrain…) et dans quelle ville ou quel quartier ?",
    "location": "Bien sûr. Dans quelle ville ou quel quartier souhaitez-vous chercher ?",
    "budget": "Quel est votre budget maximum (en FCFA) ?",
    "bedrooms": "Combien de chambres souhaitez-vous ?",
}

SKIP_WORDS = ["peu importe", "pas important", "n'importe", "nimporte", "aucune preference", "pas de preference", "pas de budget", "indifferent"]
SHOW_NOW_WORDS = [
    "affiche les resultats", "montre les resultats", "voir les resultats", "montre moi ce que tu as",
    "montre-moi ce que tu as", "affiche ce que tu as", "lance la recherche", "cherche maintenant", "ok cherche",
]
RESET_WORDS = ["nouvelle recherche", "recommencer", "recommence", "autre recherche", "on recommence", "reinitialise"]
SEARCH_VERBS = ["cherche", "recherche", "trouve", "trouver", "je veux", "je voudrais", "j'aimerais", "il me faut", "besoin d", "louer", "acheter"]


def empty_criteria():
    return {
        "transaction_type": None,
        "property_kind": None,
        "city": None,
        "neighborhood": None,
        "budget_min": None,
        "budget_max": None,
        "bedrooms": None,
        "bedrooms_mode": "min",
        "bathrooms_min": None,
        "surface_min": None,
        "surface_max": None,
        "rooms": None,
        "features": [],
        "preferences": [],
    }


def new_state():
    return {"criteria": empty_criteria(), "asked": [], "pending": None, "last_result_ids": []}


# ---------------------------------------------------------------------------
# Extraction locale (règles) — toujours disponible, même sans LLM
# ---------------------------------------------------------------------------
_NUM = r"(\d+(?:[ .  ]\d{3})*(?:[.,]\d+)?)"
_WORD_NUM = r"(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)"


def _to_int(token):
    token = token.strip()
    if token in NUMBER_WORDS:
        return NUMBER_WORDS[token]
    return int(token)


def _parse_amount(number, unit):
    """'150 000' / '150k' / '1,5 million' -> entier en FCFA."""
    raw = re.sub(r"[ .  ](?=\d{3}\b)", "", number)
    raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    unit = (unit or "").strip()
    if unit in ("k", "mille"):
        value *= 1_000
    elif unit.startswith("million") or unit in ("m", "millions", "mio"):
        value *= 1_000_000
    elif unit.startswith("milliard"):
        value *= 1_000_000_000
    return int(value) if value > 0 else None


_AMOUNT_RE = re.compile(
    _NUM + r"\s*(k|mille|millions?|milliards?|mio|m(?![²2a-z]))?\s*(f ?cfa|fcfa|cfa|xof|francs?|f(?![a-z]))?"
)


def _extract_amounts(text):
    """Retourne la liste des montants (position, valeur) qui ressemblent à un prix."""
    amounts = []
    for match in _AMOUNT_RE.finditer(text):
        number, unit, currency = match.group(1), match.group(2), match.group(3)
        following = text[match.end():match.end() + 12]
        if re.match(r"\s*(m2|m²|metres? carres?|chambres?|ch\b|pieces?|salles?|sdb|etages?)", following):
            continue
        value = _parse_amount(number, unit)
        if value is None:
            continue
        # Un « 2 » isolé n'est pas un budget ; un montant doit avoir une unité ou être >= 1000.
        if not unit and not currency and value < 1000:
            continue
        amounts.append((match.start(), value))
    return amounts


def extract_rules(message):
    """
    Extraction locale. Retourne (delta, flags) :
      - delta : uniquement les critères explicitement présents dans le message
      - flags : signaux de conversation (reset, skip, show_now, removed_features, is_search)
    """
    text = normalize(message)
    delta = {}
    flags = {
        "reset": any(w in text for w in RESET_WORDS),
        "skip": any(w in text for w in SKIP_WORDS),
        "show_now": any(w in text for w in SHOW_NOW_WORDS),
        "removed_features": [],
        "is_search": any(v in text for v in SEARCH_VERBS),
    }

    # Transaction
    if re.search(r"\b(louer|location|loyer|a louer|par mois|mensuel|/mois|bail)\b", text):
        delta["transaction_type"] = "location"
    elif re.search(r"\b(acheter|achat|a vendre|vente|acquerir|acquisition)\b", text):
        delta["transaction_type"] = "vente"

    # Type de bien
    for kind in _KIND_DETECTION_ORDER:
        keywords = PROPERTY_KINDS[kind][1]
        if any(_contains_word(text, k) for k in keywords):
            delta["property_kind"] = kind
            break

    # Ville (villes connues + villes réellement présentes en base)
    for city in _known_cities():
        if _contains_word(text, city):
            delta["city"] = city
            break

    # Quartier : « quartier X », « à X » (si X n'est pas une ville connue)
    quartier = re.search(r"quartier (?:de |d'|du )?([a-z][a-z\-']{2,})", text)
    if quartier:
        candidate = quartier.group(1)
        preference_words = {kw for _, kws in PREFERENCES.values() for kw in kws}
        if candidate not in preference_words and candidate not in _STOPWORDS:
            delta["neighborhood"] = candidate
    if "neighborhood" not in delta:
        for m in re.finditer(r"\b(?:a|au|vers|sur|dans) ([a-z][a-z\-']{3,})", text):
            word = m.group(1)
            if word in _known_cities() or word in _STOPWORDS:
                continue
            if any(word in PROPERTY_KINDS[k][1] for k in PROPERTY_KINDS):
                continue
            delta["neighborhood"] = word
            break

    # Chambres (avec mode : exact / min / max)
    bed = re.search(
        r"(au moins|minimum|min\.?|a partir de|plus de|au plus|maximum|max\.?|pas plus de|moins de|exactement|pile|seulement|uniquement)?\s*"
        + _WORD_NUM + r"\s*(chambres?|ch\b|bedrooms?)",
        text,
    )
    if bed:
        modifier = bed.group(1) or ""
        count = _to_int(bed.group(2))
        mode = "min"
        if modifier in ("exactement", "pile", "seulement", "uniquement"):
            mode = "exact"
        elif modifier in ("au plus", "maximum", "max", "max.", "pas plus de"):
            mode = "max"
        elif modifier == "moins de":
            mode, count = "max", max(count - 1, 0)
        elif modifier == "plus de":
            count += 1
        delta["bedrooms"] = count
        delta["bedrooms_mode"] = mode

    # Salles de bain
    bath = re.search(_WORD_NUM + r"\s*(salles? de bains?|sdb|douches?)", text)
    if bath:
        delta["bathrooms_min"] = _to_int(bath.group(1))

    # Pièces (non stocké en base : conservé à titre informatif)
    rooms = re.search(_WORD_NUM + r"\s*pieces?\b", text)
    if rooms:
        delta["rooms"] = _to_int(rooms.group(1))

    # Superficie
    surf = re.search(r"(au moins|minimum|plus de|au plus|maximum|moins de)?\s*(\d+)\s*(m2|m²|metres? carres?)", text)
    if surf:
        value = int(surf.group(2))
        if surf.group(1) in ("au plus", "maximum", "moins de"):
            delta["surface_max"] = value
        else:
            delta["surface_min"] = value

    # Budget
    between = re.search(r"entre " + _NUM + r"\s*(k|mille|millions?)?\s*(?:fcfa|f|cfa|xof)?\s*et " + _NUM + r"\s*(k|mille|millions?)?", text)
    if between:
        low = _parse_amount(between.group(1), between.group(2) or between.group(4))
        high = _parse_amount(between.group(3), between.group(4))
        if low and high:
            delta["budget_min"], delta["budget_max"] = min(low, high), max(low, high)
    else:
        amounts = _extract_amounts(text)
        if amounts:
            position, value = amounts[-1]
            before = text[max(0, position - 25):position]
            if re.search(r"(a partir de|minimum|au moins|pas moins de|(?<!pas )plus de)\s*$", before):
                delta["budget_min"] = value
            else:
                delta["budget_max"] = value

    # Équipements (« sans X » retire l'équipement)
    features = []
    for key, (_, _, keywords) in FEATURES.items():
        for kw in keywords:
            if _contains_word(text, kw):
                if _contains_word(text, f"sans {kw}"):
                    flags["removed_features"].append(key)
                elif key not in features:
                    features.append(key)
                break
    if "garage" in features and "parking" in features:
        features.remove("garage")  # « parking » couvre déjà le garage
    if features:
        delta["features"] = features

    # Préférences souples
    prefs = [key for key, (_, kws) in PREFERENCES.items() if any(_contains_word(text, k) for k in kws)]
    if prefs:
        delta["preferences"] = prefs

    return delta, flags


_STOPWORDS = {
    "louer", "vendre", "acheter", "partir", "moins", "plus", "prix", "budget", "maximum", "minimum",
    "proximite", "proche", "cote", "environ", "peu", "pres", "quartier", "ville", "mois", "parking",
    "calme", "deux", "trois", "quatre", "cinq", "une", "residentiel", "populaire", "chic", "securise",
    "internet", "maison", "appartement", "villa", "studio", "terrain",
}

CITY_DISPLAY = {
    "lome": "Lomé", "sokode": "Sokodé", "kpalime": "Kpalimé", "atakpame": "Atakpamé",
    "tsevie": "Tsévié", "aneho": "Aného", "notse": "Notsé",
}


def display_city(city):
    norm = normalize(city)
    return CITY_DISPLAY.get(norm, (city or "").strip().title())


def _known_cities():
    """Villes connues + villes réellement présentes dans les annonces visibles (cache 5 min)."""
    from django.core.cache import cache

    cached = cache.get("ai_search:known_cities")
    if cached is not None:
        return cached
    cities = list(KNOWN_CITIES)
    try:
        for city in visible_properties().values_list("city", flat=True).distinct()[:200]:
            norm = normalize(city)
            if norm and norm not in cities:
                cities.append(norm)
    except Exception:  # pas de base disponible (ex. import hors contexte)
        return cities
    cache.set("ai_search:known_cities", cities, 300)
    return cities


# ---------------------------------------------------------------------------
# Extraction LLM (optionnelle) + validation stricte de sa sortie
# ---------------------------------------------------------------------------
LLM_SYSTEM_PROMPT = """Tu convertis une demande de recherche immobilière (en français) en critères JSON pour DOMIORA (Togo, prix en FCFA).
Tu ne réponds QUE par un objet JSON, sans texte autour. Tu n'inventes aucun critère absent du message.
Tu reçois les critères actuels de la conversation et la dernière question posée : renvoie les critères MIS À JOUR (complets).
Si l'utilisateur commence une recherche totalement différente, repars de zéro.

Schéma :
{
 "transaction_type": "location" | "vente" | null,
 "property_kind": un de %(kinds)s ou null,
 "city": string normalisée sans accent (ex "lome") ou null,
 "neighborhood": string ou null,
 "budget_min": entier FCFA ou null,
 "budget_max": entier FCFA ou null,
 "bedrooms": entier ou null,
 "bedrooms_mode": "min" | "exact" | "max",
 "bathrooms_min": entier ou null,
 "surface_min": entier m² ou null,
 "surface_max": entier m² ou null,
 "rooms": entier (nombre de pièces) ou null,
 "features": liste parmi %(features)s,
 "preferences": liste parmi %(preferences)s,
 "show_now": booléen (l'utilisateur veut voir les résultats sans répondre aux questions),
 "skip": booléen (l'utilisateur dit que le critère demandé n'a pas d'importance)
}
Règles : "2 chambres" => bedrooms 2, mode "min" ; "exactement 2" => "exact" ; "au plus 2" => "max".
"150 000", "150k", "150 mille" => 150000 ; "1,5 million" => 1500000. Un nombre seul en réponse à la question du budget est le budget ; en réponse à la question des chambres, c'est le nombre de chambres.
"maison" => property_kind "maison". "quartier calme" => preferences ["calme"]. "avec parking" => features ["parking"].
"""


def _llm_prompt():
    return LLM_SYSTEM_PROMPT % {
        "kinds": list(PROPERTY_KINDS.keys()),
        "features": list(FEATURES.keys()),
        "preferences": list(PREFERENCES.keys()),
    }


def extract_with_llm(message, state):
    """Retourne (critères complets validés, flags) ou (None, None) si le LLM est indisponible."""
    from services import llm

    if not llm.is_configured():
        return None, None
    import json

    user_content = json.dumps(
        {
            "criteres_actuels": state["criteria"],
            "derniere_question": state.get("pending"),
            "message": message[:1000],
        },
        ensure_ascii=False,
    )
    data, _provider = llm.complete_json(
        [{"role": "system", "content": _llm_prompt()}, {"role": "user", "content": user_content}],
        max_tokens=400,
        temperature=0,
    )
    if not data:
        return None, None
    criteria = sanitize_criteria(data)
    flags = {"show_now": bool(data.get("show_now")), "skip": bool(data.get("skip"))}
    return criteria, flags


def _clean_int(value, low=0, high=10**12):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _clean_str(value, max_len=80):
    if not isinstance(value, str):
        return None
    value = re.sub(r"[^\w\s\-']", "", value, flags=re.UNICODE).strip()[:max_len]
    return normalize(value) or None


def sanitize_criteria(data):
    """Valide toute sortie (LLM ou client) contre des listes blanches."""
    clean = empty_criteria()
    if not isinstance(data, dict):
        return clean
    if data.get("transaction_type") in ("location", "vente"):
        clean["transaction_type"] = data["transaction_type"]
    if data.get("property_kind") in PROPERTY_KINDS:
        clean["property_kind"] = data["property_kind"]
    clean["city"] = _clean_str(data.get("city"))
    clean["neighborhood"] = _clean_str(data.get("neighborhood"))
    clean["budget_min"] = _clean_int(data.get("budget_min"), 1)
    clean["budget_max"] = _clean_int(data.get("budget_max"), 1)
    if clean["budget_min"] and clean["budget_max"] and clean["budget_min"] > clean["budget_max"]:
        clean["budget_min"], clean["budget_max"] = clean["budget_max"], clean["budget_min"]
    clean["bedrooms"] = _clean_int(data.get("bedrooms"), 0, 50)
    if data.get("bedrooms_mode") in ("min", "exact", "max"):
        clean["bedrooms_mode"] = data["bedrooms_mode"]
    clean["bathrooms_min"] = _clean_int(data.get("bathrooms_min"), 0, 50)
    clean["surface_min"] = _clean_int(data.get("surface_min"), 1, 1_000_000)
    clean["surface_max"] = _clean_int(data.get("surface_max"), 1, 1_000_000)
    clean["rooms"] = _clean_int(data.get("rooms"), 1, 100)
    features = data.get("features") or []
    clean["features"] = [f for f in dict.fromkeys(features) if f in FEATURES] if isinstance(features, list) else []
    prefs = data.get("preferences") or []
    clean["preferences"] = [p for p in dict.fromkeys(prefs) if p in PREFERENCES] if isinstance(prefs, list) else []
    return clean


# ---------------------------------------------------------------------------
# Conversation : fusion des critères + questions de clarification
# ---------------------------------------------------------------------------
def _merge(base, delta):
    merged = copy.deepcopy(base)
    for key, value in delta.items():
        if key == "features":
            merged["features"] = list(dict.fromkeys(merged["features"] + value))
        elif key == "preferences":
            merged["preferences"] = list(dict.fromkeys(merged["preferences"] + value))
        elif value is not None:
            merged[key] = value
    if "city" in delta and "neighborhood" not in delta:
        merged["neighborhood"] = None if base.get("city") != delta["city"] else merged["neighborhood"]
    return merged


def _answer_pending(message, pending, delta):
    """Interprète une réponse courte à la dernière question (« 200 000 », « 3 », « Kara »)."""
    text = normalize(message)
    if pending == "budget" and "budget_max" not in delta and "budget_min" not in delta:
        number = re.fullmatch(r"(?:max(?:imum)?\s*)?" + _NUM + r"\s*(k|mille|millions?)?\s*(?:f ?cfa|fcfa|cfa|f|xof)?\.?", text)
        if number:
            value = _parse_amount(number.group(1), number.group(2))
            if value and value < 1000 and not number.group(2):
                value *= 1000  # « 200 » en réponse au budget = 200 000 FCFA
            if value:
                delta["budget_max"] = value
    elif pending == "bedrooms" and "bedrooms" not in delta:
        number = re.fullmatch(r"(?:au moins |minimum |exactement )?" + _WORD_NUM + r"\.?", text)
        if number:
            delta["bedrooms"] = _to_int(number.group(1))
            delta["bedrooms_mode"] = "exact" if text.startswith("exactement") else "min"
    elif pending in ("location", "kind_location") and "city" not in delta and "neighborhood" not in delta:
        words = re.sub(r"^(a|au|sur|dans|vers)\s+", "", text).strip(" .!")
        if words and len(words.split()) <= 3 and not re.search(r"\d", words) and "property_kind" not in delta:
            delta["neighborhood" if words not in _known_cities() else "city"] = words
    return delta


def update_state(state, message, use_llm=True):
    """
    Met à jour l'état de recherche à partir d'un nouveau message.
    Retourne (state, flags).
    """
    state = copy.deepcopy(state) if state else new_state()
    state.setdefault("criteria", empty_criteria())
    state.setdefault("asked", [])
    state.setdefault("pending", None)
    state.setdefault("last_result_ids", [])

    delta, flags = extract_rules(message)
    delta = _answer_pending(message, state["pending"], delta)

    # Nouvelle recherche explicite : nouveau type de bien annoncé avec un verbe de recherche
    current = state["criteria"]
    new_search = flags["reset"] or (
        flags["is_search"]
        and delta.get("property_kind")
        and current.get("property_kind")
        and delta["property_kind"] != current["property_kind"]
    )
    if new_search:
        state = new_state()
        current = state["criteria"]

    llm_criteria, llm_flags = (None, None)
    if use_llm:
        try:
            llm_criteria, llm_flags = extract_with_llm(message, state)
        except Exception:  # le LLM ne doit jamais casser la recherche
            logger.exception("LLM criteria extraction failed")
            llm_criteria = None

    if llm_criteria is not None:
        # Le LLM renvoie l'état complet ; les règles locales complètent ce qu'il aurait manqué.
        criteria = llm_criteria
        for key, value in delta.items():
            if key in ("features", "preferences"):
                criteria[key] = list(dict.fromkeys(criteria[key] + value))
            elif criteria.get(key) in (None, "min") and value is not None:
                criteria[key] = value
        flags["show_now"] = flags["show_now"] or llm_flags.get("show_now", False)
        flags["skip"] = flags["skip"] or llm_flags.get("skip", False)
    else:
        criteria = _merge(current, delta)

    for removed in flags["removed_features"]:
        if removed in criteria["features"]:
            criteria["features"].remove(removed)

    state["criteria"] = sanitize_criteria(criteria)
    return state, flags


def next_question(state, flags=None):
    """Prochaine question utile (au plus une par tour, chacune posée une seule fois)."""
    flags = flags or {}
    if flags.get("show_now"):
        return None
    c, asked = state["criteria"], state["asked"]
    has_location = bool(c["city"] or c["neighborhood"])
    if not has_location and not c["property_kind"] and not _has_any_constraint(c):
        return None if "kind_location" in asked else "kind_location"
    if not has_location and "location" not in asked and "kind_location" not in asked:
        return "location"
    if c["budget_max"] is None and c["budget_min"] is None and "budget" not in asked:
        return "budget"
    if c["bedrooms"] is None and c["property_kind"] not in NON_RESIDENTIAL_KINDS and "bedrooms" not in asked:
        return "bedrooms"
    return None


def _has_any_constraint(c):
    return any(
        c[k] for k in ("transaction_type", "budget_min", "budget_max", "bedrooms", "surface_min", "surface_max", "features", "preferences")
    )


# ---------------------------------------------------------------------------
# Accès aux données : même règle de visibilité que le catalogue public
# ---------------------------------------------------------------------------
def visible_properties():
    """
    Biens que l'IA a le droit de proposer : la règle publique existante
    (_public_contactable_properties) + disponible + propriétaire vérifié.
    """
    from accounts.models import User
    from properties.models import Property
    from properties.views import _public_contactable_properties

    return _public_contactable_properties().filter(
        status=Property.Status.DISPONIBLE,
        owner__verification_status=User.VerificationStatus.APPROVED,
    )


def _candidate_queryset(criteria):
    """Pré-filtrage en base (large) ; l'évaluation fine se fait ensuite en Python."""
    qs = visible_properties()
    if criteria["transaction_type"]:
        qs = qs.filter(transaction_type=criteria["transaction_type"])
    if criteria["property_kind"]:
        _, _, exact, near = PROPERTY_KINDS[criteria["property_kind"]]
        qs = qs.filter(property_type__in=exact + near)
    if criteria["budget_max"]:
        qs = qs.filter(price__lte=Decimal(criteria["budget_max"]) * Decimal(1 + BUDGET_TOLERANCE))
    if criteria["bedrooms"] is not None and criteria["bedrooms_mode"] in ("min", "exact"):
        qs = qs.filter(bedrooms__gte=max(criteria["bedrooms"] - 1, 0))
    return qs.select_related("owner").prefetch_related("images", "amenities").order_by("-created_at")[:MAX_CANDIDATES]


# ---------------------------------------------------------------------------
# Évaluation et pertinence
# ---------------------------------------------------------------------------
OK, NEAR, FAIL, UNKNOWN = "ok", "near", "fail", "unknown"


def _fmt_money(value):
    return f"{int(value):,}".replace(",", " ") + " FCFA"


def _property_text(prop):
    return normalize(" ".join(filter(None, [prop.title, prop.description, prop.neighborhood, prop.address])))


def evaluate(prop, criteria):
    """
    Évalue un bien par rapport aux critères.
    Retourne {"checks": [(statut, texte, dur)], "excluded": bool, "score": float}.
    `dur` = critère qui conditionne une correspondance exacte.
    """
    checks = []
    excluded = False
    score = 0.0
    text = _property_text(prop)

    # Transaction
    if criteria["transaction_type"]:
        if prop.transaction_type == criteria["transaction_type"]:
            checks.append((OK, "À louer" if prop.transaction_type == "location" else "À vendre", True))
        else:
            excluded = True

    # Ville
    if criteria["city"]:
        city = normalize(prop.city)
        wanted = normalize(criteria["city"])
        if city == wanted or (len(wanted) >= 4 and (wanted in city or city in wanted)):
            checks.append((OK, display_city(prop.city), True))
        else:
            excluded = True

    # Type
    if criteria["property_kind"]:
        label, _, exact, near = PROPERTY_KINDS[criteria["property_kind"]]
        if prop.property_type in exact:
            checks.append((OK, prop.get_property_type_display(), True))
        elif prop.property_type in near:
            checks.append((NEAR, f"Type proche : {prop.get_property_type_display()} (demandé : {label.lower()})", True))
            score -= 2
        else:
            excluded = True

    # Budget
    local_currency = normalize(prop.currency) in LOCAL_CURRENCIES or not prop.currency
    price = float(prop.price)
    if criteria["budget_max"] or criteria["budget_min"]:
        if not local_currency:
            checks.append((UNKNOWN, f"Prix en {prop.currency} : comparaison au budget impossible", True))
        else:
            budget_max, budget_min = criteria["budget_max"], criteria["budget_min"]
            if budget_max and price > budget_max:
                over = (price - budget_max) / budget_max
                if over <= BUDGET_TOLERANCE:
                    checks.append((NEAR, f"Au-dessus du budget de {round(over * 100)} % ({prop.price_display})", True))
                    score -= 3 * over * 10
                else:
                    excluded = True
            elif budget_min and price < budget_min:
                checks.append((NEAR, f"Sous le budget minimum ({prop.price_display})", True))
                score -= 1
            else:
                checks.append((OK, f"Budget respecté ({prop.price_display})", True))
                if budget_max:
                    score += 1 - (budget_max - price) / budget_max * 0.5  # proche du budget = mieux exploité

    # Chambres
    wanted_bed = criteria["bedrooms"]
    if wanted_bed is not None:
        beds = prop.bedrooms
        mode = criteria["bedrooms_mode"]
        plural = lambda n: f"{n} chambre{'s' if n > 1 else ''}"
        if beds == 0 and prop.property_type not in ("terrain", "commercial"):
            checks.append((UNKNOWN, "Nombre de chambres non renseigné", True))
        elif mode == "exact":
            if beds == wanted_bed:
                checks.append((OK, plural(beds), True))
                score += 1
            elif abs(beds - wanted_bed) == 1:
                checks.append((NEAR, f"{plural(beds)} (demandé : exactement {wanted_bed})", True))
            else:
                excluded = True
        elif mode == "max":
            if beds <= wanted_bed:
                checks.append((OK, plural(beds), True))
            elif beds == wanted_bed + 1:
                checks.append((NEAR, f"{plural(beds)} (demandé : {wanted_bed} au plus)", True))
            else:
                excluded = True
        else:  # minimum
            if beds >= wanted_bed:
                checks.append((OK, plural(beds), True))
                score += 1 if beds == wanted_bed else 0.5
            elif beds == wanted_bed - 1:
                checks.append((NEAR, f"{plural(beds)} (demandé : {wanted_bed} minimum)", True))
            else:
                excluded = True

    # Salles de bain
    if criteria["bathrooms_min"]:
        if not prop.bathrooms:
            checks.append((UNKNOWN, "Salles de bain non renseignées", True))
        elif prop.bathrooms >= criteria["bathrooms_min"]:
            checks.append((OK, f"{prop.bathrooms} salle(s) de bain", True))
        else:
            checks.append((NEAR, f"{prop.bathrooms} salle(s) de bain (demandé : {criteria['bathrooms_min']})", True))

    # Superficie (0 = non renseignée)
    surface = float(prop.surface_area or 0)
    if criteria["surface_min"] or criteria["surface_max"]:
        if surface <= 1:
            checks.append((UNKNOWN, "Superficie non renseignée", True))
        elif criteria["surface_min"] and surface < criteria["surface_min"]:
            gap = (criteria["surface_min"] - surface) / criteria["surface_min"]
            if gap <= 0.2:
                checks.append((NEAR, f"{surface:.0f} m² (demandé : {criteria['surface_min']} m² minimum)", True))
            else:
                excluded = True
        elif criteria["surface_max"] and surface > criteria["surface_max"]:
            checks.append((NEAR, f"{surface:.0f} m² (demandé : {criteria['surface_max']} m² maximum)", True))
        else:
            checks.append((OK, f"Superficie {surface:.0f} m²", True))

    # Équipements demandés : confirmés par les équipements enregistrés ou le texte de l'annonce
    for key in criteria["features"]:
        label, aliases, keywords = FEATURES[key]
        matched = next((a for a in prop.amenities.all() if any(alias in normalize(a.name) for alias in aliases)), None)
        in_text = any(_contains_word(text, kw) for kw in keywords)
        if matched:
            detail = "" if normalize(matched.name) == normalize(label) else f" ({matched.name})"
            checks.append((OK, f"{label} disponible{detail}", True))
            score += 0.5
        elif in_text:
            checks.append((OK, f"{label} mentionné dans l'annonce", True))
            score += 0.3
        else:
            checks.append((NEAR, f"{label} non indiqué dans l'annonce", True))

    # Quartier (souple)
    if criteria["neighborhood"]:
        wanted = normalize(criteria["neighborhood"])
        if _contains_word(text, wanted) or wanted in normalize(prop.neighborhood):
            checks.append((OK, f"Quartier demandé ({criteria['neighborhood'].title()})", False))
            score += 2
        elif prop.neighborhood:
            checks.append((NEAR, f"Quartier différent ({prop.neighborhood})", False))
        else:
            checks.append((UNKNOWN, "Quartier non précisé dans l'annonce", False))

    # Préférences (souples, jamais supposées)
    for key in criteria["preferences"]:
        label, keywords = PREFERENCES[key]
        if any(_contains_word(text, kw) for kw in keywords):
            checks.append((OK, f"{label} (mentionné dans l'annonce)", False))
            score += 0.5
        else:
            checks.append((UNKNOWN, f"{label} : information non renseignée", False))

    # Signaux de confiance (n'influencent que l'ordre)
    if prop.owner_verified:
        score += 0.3
    if prop.images.all():
        score += 0.2

    return {"checks": checks, "excluded": excluded, "score": score}


def classify(evaluation):
    """Niveau de correspondance compréhensible (pas de pourcentage artificiel)."""
    if not evaluation["checks"]:
        return "available"  # aucun critère : on ne prétend pas à une « correspondance »
    hard = [c for c in evaluation["checks"] if c[2]]
    soft = [c for c in evaluation["checks"] if not c[2]]
    if any(status != OK for status, _, _ in hard):
        return "partial"
    if any(status != OK for status, _, _ in soft):
        return "good"
    return "excellent"


MATCH_LABELS = {
    "excellent": "Très bon match",
    "good": "Bon match",
    "partial": "Correspondance partielle",
    "available": "Bien disponible",
}
STATUS_SYMBOLS = {OK: "✓", NEAR: "△", FAIL: "✗", UNKNOWN: "•"}


def serialize_property(prop, evaluation=None, level=None):
    """Données publiques uniquement (aucun contact ni donnée administrative)."""
    surface = float(prop.surface_area or 0)
    data = {
        "id": prop.pk,
        "title": prop.title,
        "url": prop.get_absolute_url(),
        "image": prop.primary_image,
        "price": prop.price_display,
        "city": display_city(prop.city),
        "neighborhood": prop.neighborhood,
        "property_type": prop.get_property_type_display(),
        "transaction": prop.get_transaction_type_display(),
        "bedrooms": prop.bedrooms or None,
        "bathrooms": prop.bathrooms or None,
        "surface": round(surface) if surface > 1 else None,
        "owner_verified": prop.owner_verified,
    }
    if evaluation is not None:
        data["match_level"] = level
        data["match_label"] = MATCH_LABELS[level]
        data["reasons"] = [
            {"status": status, "symbol": STATUS_SYMBOLS[status], "text": label}
            for status, label, _ in evaluation["checks"]
        ]
    return data


def criteria_summary(criteria):
    """Liste lisible des critères compris (affichée à l'utilisateur)."""
    items = []
    if criteria["property_kind"]:
        items.append(PROPERTY_KINDS[criteria["property_kind"]][0])
    if criteria["transaction_type"]:
        items.append("Location" if criteria["transaction_type"] == "location" else "Achat")
    if criteria["city"]:
        items.append(display_city(criteria["city"]))
    if criteria["neighborhood"]:
        items.append(f"Quartier : {criteria['neighborhood'].title()}")
    if criteria["bedrooms"] is not None:
        n = criteria["bedrooms"]
        suffix = {"min": " minimum", "exact": " exactement", "max": " maximum"}[criteria["bedrooms_mode"]]
        items.append(f"{n} chambre{'s' if n > 1 else ''}{suffix}")
    if criteria["bathrooms_min"]:
        items.append(f"{criteria['bathrooms_min']} salle(s) de bain minimum")
    if criteria["budget_min"] and criteria["budget_max"]:
        items.append(f"Budget : {_fmt_money(criteria['budget_min'])} – {_fmt_money(criteria['budget_max'])}")
    elif criteria["budget_max"]:
        items.append(f"Budget maximum : {_fmt_money(criteria['budget_max'])}")
    elif criteria["budget_min"]:
        items.append(f"Budget minimum : {_fmt_money(criteria['budget_min'])}")
    if criteria["surface_min"]:
        items.append(f"{criteria['surface_min']} m² minimum")
    if criteria["surface_max"]:
        items.append(f"{criteria['surface_max']} m² maximum")
    items.extend(FEATURES[f][0] for f in criteria["features"])
    items.extend(PREFERENCES[p][0] for p in criteria["preferences"])
    return items


def search(criteria):
    """
    Recherche dans les biens réellement visibles.
    Retourne {"exact": [(prop, evaluation, level)], "alternatives": [...]}.
    """
    exact, alternatives = [], []
    for prop in _candidate_queryset(criteria):
        evaluation = evaluate(prop, criteria)
        if evaluation["excluded"]:
            continue
        level = classify(evaluation)
        if level == "partial":
            near_count = sum(1 for s, _, hard in evaluation["checks"] if hard and s != OK)
            if near_count <= 2:
                evaluation["score"] -= near_count * 2
                alternatives.append((prop, evaluation, level))
        else:
            exact.append((prop, evaluation, level))

    level_rank = {"excellent": 3, "good": 2, "available": 1, "partial": 0}
    exact.sort(key=lambda item: (level_rank[item[2]], item[1]["score"]), reverse=True)
    alternatives.sort(key=lambda item: item[1]["score"], reverse=True)
    return {"exact": exact[:MAX_RESULTS], "alternatives": alternatives[:MAX_ALTERNATIVES]}


# ---------------------------------------------------------------------------
# Point d'entrée conversationnel (utilisé par la page IA et, au bloc C, par l'assistant)
# ---------------------------------------------------------------------------
NO_EXACT_MESSAGE = "Aucun bien ne correspond exactement à votre recherche actuellement."


def _notes(criteria):
    if criteria["rooms"]:
        return [
            f"Nombre de pièces ({criteria['rooms']}) : cette information n'est pas enregistrée dans les annonces DOMIORA, "
            "la recherche s'appuie sur le nombre de chambres."
        ]
    return []


def run_conversation_turn(state, message, use_llm=True, show_now=False):
    """
    Traite un message utilisateur. Retourne (nouvel_état, réponse_json_sérialisable).
    `show_now=True` affiche directement les résultats sans question de clarification.
    """
    state, flags = update_state(state, message, use_llm=use_llm)
    if show_now:
        flags["show_now"] = True
    criteria = state["criteria"]
    summary = criteria_summary(criteria)
    notes = _notes(criteria)

    question_key = next_question(state, flags)
    if question_key:
        state["pending"] = question_key
        state["asked"].append(question_key)
        intro = ""
        if summary:
            intro = "Très bien. J'ai noté : " + ", ".join(summary) + ". "
        return state, {
            "status": "question",
            "message": intro + QUESTIONS[question_key],
            "question": QUESTIONS[question_key],
            "question_key": question_key,
            "criteria": criteria,
            "criteria_summary": summary,
            "results": [],
            "alternatives": [],
            "notes": notes,
        }

    return search_now(state)


def search_now(state):
    """Lance la recherche avec les critères actuels de l'état (sans analyser de message)."""
    criteria = state["criteria"]
    summary = criteria_summary(criteria)
    notes = _notes(criteria)
    state["pending"] = None
    found = search(criteria)
    results = [serialize_property(p, e, lvl) for p, e, lvl in found["exact"]]
    alternatives = [serialize_property(p, e, lvl) for p, e, lvl in found["alternatives"]]
    state["last_result_ids"] = [r["id"] for r in results] + [a["id"] for a in alternatives]

    if results:
        status = "results"
        count = len(results)
        message_text = f"J'ai trouvé {count} bien{'s' if count > 1 else ''} correspondant à votre recherche, classé{'s' if count > 1 else ''} par pertinence."
        if alternatives:
            message_text += " J'ajoute quelques biens proches, présentés séparément."
    elif alternatives:
        status = "no_exact"
        n = len(alternatives)
        message_text = f"{NO_EXACT_MESSAGE} Voici {n} bien{'s' if n > 1 else ''} qui s'en rapproche{'nt' if n > 1 else ''}."
    else:
        status = "none"
        message_text = NO_EXACT_MESSAGE + " Essayez d'élargir votre budget, la zone ou le nombre de chambres, ou enregistrez une alerte pour être prévenu."

    return state, {
        "status": status,
        "message": message_text,
        "question": None,
        "question_key": None,
        "criteria": criteria,
        "criteria_summary": summary,
        "results": results,
        "alternatives": alternatives,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Compatibilité avec l'ancien assistant (format de critères historique)
# ---------------------------------------------------------------------------
_LEGACY_KIND = {
    "apartment": "appartement", "house": "maison", "villa": "villa", "studio": "studio",
    "terrain": "terrain", "duplex": "duplex", "appartement": "appartement", "maison": "maison",
}


def legacy_search(old_criteria, limit=5):
    """Adapte l'ancien format {'city','bedrooms','property_type','transaction_type','budget'}."""
    from properties.models import Property

    criteria = empty_criteria()
    if old_criteria.get("city"):
        criteria["city"] = normalize(old_criteria["city"])
    if old_criteria.get("bedrooms"):
        criteria["bedrooms"] = _clean_int(old_criteria["bedrooms"], 0, 50)
    kind = _LEGACY_KIND.get(old_criteria.get("property_type"))
    if kind:
        criteria["property_kind"] = kind
    transaction = {"rent": "location", "sale": "vente"}.get(old_criteria.get("transaction_type"), old_criteria.get("transaction_type"))
    if transaction in ("location", "vente"):
        criteria["transaction_type"] = transaction
    budget = _clean_int(old_criteria.get("budget"), 1)
    if budget:
        criteria["budget_max"] = budget if budget >= 1000 else budget * 1000

    ids = [p.pk for p, _, _ in search(criteria)["exact"]][:limit]
    if not ids:
        return Property.objects.none()
    from django.db.models import Case, IntegerField, When

    ordering = Case(*[When(pk=pk, then=i) for i, pk in enumerate(ids)], output_field=IntegerField())
    return Property.objects.filter(pk__in=ids).order_by(ordering)
