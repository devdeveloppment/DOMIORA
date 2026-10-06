"""
DOMIORA AI Assistant
====================

Pont entre le widget de chat (core.views.assistant_chat) et l'Assistant
DOMIORA conversationnel de services/ai_assistant.py.
"""
import logging

logger = logging.getLogger(__name__)

FAILURE_REPLY = (
    "Désolé, je rencontre un problème momentané. Vous pouvez réessayer dans un instant, "
    "ou parcourir directement les annonces DOMIORA."
)


def get_assistant_reply(message, conversation_history=None, user=None, state=None):
    """
    Point d'entrée utilisé par le widget.

    `conversation_history` (envoyé par le navigateur) est conservé pour compatibilité
    mais n'est plus utilisé : l'historique fiable est stocké côté serveur dans `state`.

    Returns:
        dict: {
            'reply': str,
            'matches': list de cartes de biens (dict publics),
            'source': str,
            'state': nouvel état de conversation à stocker en session,
            + 'cards', 'actions', 'comparison', 'criteria_summary', 'quick_replies', 'intent'
        }
    """
    from services.ai_assistant import handle_assistant_message

    try:
        new_state, result = handle_assistant_message(message, user=user, state=state)
    except Exception:
        logger.exception("Assistant DOMIORA failure")
        return {"reply": FAILURE_REPLY, "matches": [], "source": "error", "state": state, "intent": "error"}

    result["matches"] = result.get("cards", [])
    result["state"] = new_state
    return result
