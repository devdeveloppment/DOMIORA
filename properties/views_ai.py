"""Vues de la recherche immobilière intelligente et de l'analyse IA du comparateur."""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from services import property_compare, property_search
from services.rate_limit import is_rate_limited

from .views import _public_contactable_properties

logger = logging.getLogger(__name__)

SESSION_KEY = "ai_search_state"
MAX_MESSAGE_LENGTH = 1000
RATE_LIMITED_MESSAGE = "Vous avez envoyé beaucoup de demandes en peu de temps. Merci de patienter une minute avant de réessayer."


def ai_search(request):
    """Page « Recherche avec l'IA ». `?q=` permet de lancer directement une recherche."""
    return render(request, "properties/ai_search.html", {"initial_query": request.GET.get("q", "")[:MAX_MESSAGE_LENGTH]})


@require_POST
def ai_search_api(request):
    """
    POST JSON {"message": "..."} ou {"reset": true}.
    L'état de la recherche est conservé côté serveur dans la session.
    """
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    if payload.get("reset"):
        request.session[SESSION_KEY] = property_search.new_state()
        return JsonResponse({"status": "reset", "message": "Nouvelle recherche : décrivez le bien que vous recherchez."})

    message = payload.get("message")
    message = message.strip() if isinstance(message, str) else ""
    if not message:
        return JsonResponse({"error": "Le message est vide."}, status=400)
    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse({"error": "Le message est trop long (1000 caractères maximum)."}, status=400)

    if is_rate_limited(request, "ai_search"):
        return JsonResponse({"error": RATE_LIMITED_MESSAGE}, status=429)

    state = request.session.get(SESSION_KEY) or property_search.new_state()
    try:
        state, result = property_search.run_conversation_turn(state, message)
    except Exception:
        logger.exception("AI search failed")
        return JsonResponse({"error": "La recherche a rencontré un problème. Merci de réessayer."}, status=500)

    request.session[SESSION_KEY] = state
    return JsonResponse(result)


@require_GET
def compare_analysis(request):
    """Analyse IA des biens du comparateur (mêmes règles de visibilité que la page de comparaison)."""
    ids = [i for i in request.GET.get("ids", "").split(",") if i.isdigit()][:3]
    if len(ids) < 2:
        return JsonResponse({"error": "Sélectionnez au moins deux biens à comparer."}, status=400)
    if is_rate_limited(request, "ai_compare"):
        return JsonResponse({"error": RATE_LIMITED_MESSAGE}, status=429)

    properties = list(
        _public_contactable_properties().filter(pk__in=ids).select_related("owner").prefetch_related("amenities", "images")
    )
    properties.sort(key=lambda item: ids.index(str(item.pk)))
    if len(properties) < 2:
        return JsonResponse({"error": "Ces biens ne sont plus disponibles à la comparaison."}, status=404)
    return JsonResponse(property_compare.compare(properties))
