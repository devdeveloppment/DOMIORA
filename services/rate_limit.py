"""
Limitation simple du nombre de requêtes vers les fonctionnalités IA.

Basée sur le cache Django (LocMem par défaut : compteur par processus ;
partagé entre workers si le cache est configuré sur Redis).
"""
from django.conf import settings
from django.core.cache import cache


def client_identifier(request):
    """Identifiant stable : utilisateur connecté, sinon IP (derrière le proxy Render)."""
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        return f"user:{request.user.pk}"
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


def is_rate_limited(request, scope, limit=None, window=None):
    """
    Incrémente le compteur de `scope` pour ce client et retourne True si la
    limite est dépassée sur la fenêtre courante.
    """
    limit = limit or getattr(settings, "AI_RATE_LIMIT", 20)
    window = window or getattr(settings, "AI_RATE_WINDOW_SECONDS", 60)
    key = f"ratelimit:{scope}:{client_identifier(request)}"
    if cache.add(key, 1, timeout=window):
        return False
    try:
        count = cache.incr(key)
    except ValueError:  # clé expirée entre add() et incr()
        cache.set(key, 1, timeout=window)
        return False
    return count > limit
