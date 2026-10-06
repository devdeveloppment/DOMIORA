"""
Contrôles Django (`manage.py check`) de la configuration de production des visites virtuelles.

En production (DEBUG=False), la génération exige :
- REDIS_URL : broker partagé entre le service web et le worker Celery ;
- CLOUDINARY_URL : stockage durable des vidéos (le disque Render est éphémère).
"""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def virtual_tour_production_checks(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    messages = []
    if not getattr(settings, "REDIS_URL", ""):
        messages.append(Warning(
            "REDIS_URL n'est pas défini : les visites virtuelles ne seront jamais générées en production "
            "(le broker filesystem n'est pas partagé entre le service web et le worker).",
            hint="Définir REDIS_URL (Render Key Value) sur le service web et sur le worker Celery.",
            id="domiora.W001",
        ))
    if not getattr(settings, "CLOUDINARY_URL", None):
        messages.append(Warning(
            "CLOUDINARY_URL n'est pas défini : les vidéos seraient écrites sur le disque éphémère de Render.",
            hint="Définir la même valeur CLOUDINARY_URL sur le service web et sur le worker Celery.",
            id="domiora.W002",
        ))
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        messages.append(Warning(
            "CELERY_TASK_ALWAYS_EAGER est actif : la génération vidéo bloquerait les requêtes HTTP.",
            id="domiora.W003",
        ))
    return messages
