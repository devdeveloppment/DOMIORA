"""
DOMIORA AI Assistant
====================

Two-tier design:

1. If ``ANTHROPIC_API_KEY`` is set in the environment (.env), every message is sent
   to the real Claude API (Messages endpoint) with a system prompt describing
   DOMIORA, plus a short grounding context built from a keyword search against
   the live Property catalogue (lightweight RAG). This gives genuinely useful,
   natural-language answers.

2. If no key is configured, a rule-based fallback still provides real value:
   it parses the message for a city, a max budget, a transaction type
   (vente/location) and a property type, and returns actual matching listings
   from the database — so the assistant is useful out of the box, with zero
   external dependency or cost.

To enable tier 1, add to your `.env`:
    ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
"""
import os
import re
import requests
from django.conf import settings

from properties.models import Property

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

CITY_PATTERN = re.compile(
    r"\b(brooklyn|new york|henderson|bronx|las vegas|hoboken|beverly hills|westport|"
    r"queens|dallas|jersey city|naples|paris|lyon|lom[ée])\b", re.IGNORECASE
)
PRICE_PATTERN = re.compile(r"(\d[\d\s]{2,})\s?(?:\$|usd|dollars?|euros?)?", re.IGNORECASE)
TYPE_KEYWORDS = {
    "studio": "studio", "villa": "villa", "penthouse": "penthouse", "loft": "loft",
    "duplex": "duplex", "triplex": "triplex", "appartement": "appartement", "appart": "appartement",
    "maison": "maison_de_ville", "château": "chateau", "chateau": "chateau", "ferme": "ferme",
    "bungalow": "bungalow", "cottage": "cottage", "ranch": "ranch", "terrain": "terrain",
}


def _build_grounding_context(message):
    """Search the live catalogue for properties relevant to the user's message."""
    qs = Property.objects.filter(is_published=True)
    city_match = CITY_PATTERN.search(message)
    if city_match:
        qs = qs.filter(city__icontains=city_match.group(1))
    if any(w in message.lower() for w in ["louer", "location", "locataire"]):
        qs = qs.filter(transaction_type="location")
    elif any(w in message.lower() for w in ["acheter", "achat", "vendre", "vente"]):
        qs = qs.filter(transaction_type="vente")
    for kw, ptype in TYPE_KEYWORDS.items():
        if kw in message.lower():
            qs = qs.filter(property_type=ptype)
            break
    price_match = PRICE_PATTERN.search(message)
    if price_match:
        try:
            budget = int(price_match.group(1).replace(" ", ""))
            if budget > 1000:
                qs = qs.filter(price__lte=budget)
        except ValueError:
            pass
    return list(qs[:5])


def _rule_based_reply(message, matches):
    msg = message.lower().strip()
    if any(g in msg for g in ["bonjour", "salut", "hello", "bonsoir"]):
        return "Bonjour 👋 Je suis l'assistant DOMIORA. Dites-moi ce que vous cherchez (ville, type de bien, budget, vente ou location) et je vous propose des biens correspondants."
    if "contact" in msg or "agent" in msg and "parler" in msg:
        return "Vous pouvez contacter directement un agent depuis la fiche d'un bien, ou consulter notre page « Nos agents » pour choisir un expert par spécialité."
    if "comment" in msg and ("louer" in msg or "acheter" in msg):
        return "C'est simple : 1) recherchez un bien via les filtres, 2) ouvrez la fiche du bien, 3) envoyez une demande à l'agent (visite, location ou achat), 4) l'agent valide votre demande et vous accompagne jusqu'à la transaction."
    if matches:
        lines = [f"J'ai trouvé {len(matches)} bien(s) qui pourrai(en)t vous intéresser :"]
        for p in matches:
            lines.append(f"• {p.title} — {p.price_display} — {p.city}, {p.country} ({p.bedrooms} ch.)")
        lines.append("Cliquez sur une fiche pour voir le détail et contacter l'agent.")
        return "\n".join(lines)
    return (
        "Je n'ai pas trouvé de bien correspondant précisément à votre demande. "
        "Essayez de préciser une ville, un type de bien (villa, appartement, studio...), "
        "un budget ou « vente »/« location » — par exemple : "
        "« villa à louer à Brooklyn sous 3000 »."
    )


def _call_gemini(message, matches, conversation_history=None):
    api_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return None

    context_lines = []
    for p in matches:
        context_lines.append(
            f"- {p.title} | {p.get_property_type_display()} | {p.price_display} | "
            f"{p.city}, {p.country} | {p.bedrooms} ch. / {p.bathrooms} sdb. / {p.surface_area} m² | "
            f"lien: {p.get_absolute_url()}"
        )
    context = "\n".join(context_lines) or "(aucun bien ne correspond précisément à la recherche actuelle)"

    system_prompt = (
        "Tu es l'assistant virtuel de DOMIORA, une plateforme immobilière premium. "
        "Tu aides les visiteurs à trouver un bien à acheter ou louer, tu réponds aux questions "
        "fréquentes sur le processus (visite, demande, validation, transaction) et tu donnes des "
        "conseils généraux d'achat/location. Sois concis, chaleureux et professionnel, en français. "
        "Si des biens pertinents sont listés ci-dessous, mentionne-les avec leur prix et propose le lien. "
        "Tu peux aussi faire des recommandations basées sur les critères. "
        "Ne jamais inventer un bien qui n'est pas dans la liste fournie.\n\n"
        f"Biens potentiellement pertinents pour cette conversation :\n{context}"
    )

    contents = []
    if conversation_history:
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    contents.append({"role": "user", "parts": [{"text": message}]})

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500,
                }
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return None
    except Exception:
        return None


def get_assistant_reply(message, conversation_history=None):
    """Main entry point used by the chat widget view."""
    matches = _build_grounding_context(message)
    ai_reply = _call_gemini(message, matches, conversation_history)
    if ai_reply:
        return {"reply": ai_reply, "matches": matches, "source": "gemini"}
    return {"reply": _rule_based_reply(message, matches), "matches": matches, "source": "rule_based"}
