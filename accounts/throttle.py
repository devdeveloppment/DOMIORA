"""
Limitation des tentatives de connexion échouées (anti force brute), par adresse IP et identifiant.
Après LOGIN_MAX_FAILURES échecs en LOGIN_LOCK_SECONDS, la connexion est refusée temporairement,
avec le même message que l'identifiant existe ou non.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache

LOCKED_MESSAGE = "Trop de tentatives de connexion. Patientez quelques minutes avant de réessayer."


def _limits():
    return getattr(settings, "LOGIN_MAX_FAILURES", 8), getattr(settings, "LOGIN_LOCK_SECONDS", 900)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")) or "inconnue"


def _key(request, identifier):
    raw = f"{client_ip(request)}|{(identifier or '').strip().lower()}"
    return "login-fail:" + hashlib.sha256(raw.encode()).hexdigest()


def is_locked(request, identifier):
    maximum, _ = _limits()
    return cache.get(_key(request, identifier), 0) >= maximum


def register_failure(request, identifier):
    _, seconds = _limits()
    key = _key(request, identifier)
    if cache.add(key, 1, seconds):
        return
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, seconds)


def reset(request, identifier):
    cache.delete(_key(request, identifier))
