"""
Couche d'accès aux fournisseurs LLM de DOMIORA.

Chaîne de fournisseurs : Anthropic (Claude) en priorité, puis Mistral en secours.
Les clés viennent exclusivement des settings (variables d'environnement).
Si aucun fournisseur ne répond, on retourne une chaîne vide et l'appelant
utilise sa solution locale.
"""
import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (5, 15)
# Claude réfléchit avant de répondre : délai de lecture plus large (secondes : lecture, connexion).
ANTHROPIC_TIMEOUT = (45.0, 5.0)
# Les tokens de réflexion comptent dans max_tokens : marge minimale.
ANTHROPIC_MIN_MAX_TOKENS = 4000


def is_configured():
    """Indique si au moins un fournisseur LLM est configuré."""
    return bool(getattr(settings, "MISTRAL_API_KEY", "") or getattr(settings, "ANTHROPIC_API_KEY", ""))


def complete(messages, *, max_tokens=600, temperature=0.2, json_mode=False, timeout=DEFAULT_TIMEOUT):
    """
    Envoie `messages` (format OpenAI : system/user/assistant) au premier
    fournisseur disponible. Retourne (texte, nom_fournisseur) ou ("", None).
    """
    providers = []
    anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if anthropic_key:
        providers.append(("Anthropic", lambda: _anthropic(anthropic_key, messages, max_tokens)))
    mistral_key = getattr(settings, "MISTRAL_API_KEY", "")
    if mistral_key:
        providers.append(("Mistral", lambda: _mistral(mistral_key, messages, max_tokens, temperature, json_mode, timeout)))

    for name, call in providers:
        try:
            text = call()
            if text:
                return text, name
        except Exception as error:  # réseau, quota, format inattendu...
            logger.warning("LLM provider %s failed (%s)", name, type(error).__name__)
    return "", None


def complete_json(messages, **kwargs):
    """Comme `complete`, mais retourne un dict parsé (ou None si invalide)."""
    text, provider = complete(messages, json_mode=True, **kwargs)
    if not text:
        return None, None
    data = parse_json_object(text)
    return data, provider if data is not None else None


def parse_json_object(text):
    """Extrait le premier objet JSON d'une réponse de modèle."""
    if not isinstance(text, str):
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except ValueError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _mistral(api_key, messages, max_tokens, temperature, json_mode, timeout):
    payload = {
        "model": getattr(settings, "MISTRAL_MODEL", "mistral-small-latest"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    choices = response.json().get("choices", [])
    if not choices:
        return ""
    return (choices[0].get("message", {}).get("content") or "").strip()


def _anthropic(api_key, messages, max_tokens):
    """
    Appel Claude via le SDK officiel. Le modèle (Claude Sonnet 5.5 par défaut)
    réfléchit de façon adaptative ; `temperature` n'est pas transmise car les
    modèles récents refusent les valeurs non par défaut.
    """
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    conversation = [m for m in messages if m["role"] in ("user", "assistant")]
    # Import à la demande : le SDK est lourd ; chargé au démarrage, il retardait la première requête
    # au point de dépasser le délai de gunicorn sur l'instance gratuite de Render.
    import anthropic

    read, connect = ANTHROPIC_TIMEOUT
    client = anthropic.Anthropic(api_key=api_key, timeout=anthropic.Timeout(read, connect=connect), max_retries=1)
    response = client.beta.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        system=system,
        messages=conversation,
        max_tokens=max(max_tokens, ANTHROPIC_MIN_MAX_TOKENS),
        output_config={"effort": getattr(settings, "ANTHROPIC_EFFORT", "low")},
        # En cas de refus par les filtres de sécurité, l'API relance sur un modèle de secours.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return ""
    return "\n".join(b.text.strip() for b in response.content if b.type == "text").strip()
