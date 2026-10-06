"""Tâches Celery du module properties."""
from celery import shared_task
from django.conf import settings


@shared_task(
    name="properties.tasks.generate_virtual_tour_task",
    acks_late=True,
    soft_time_limit=settings.VIRTUAL_TOUR_SOFT_TIME_LIMIT,
    time_limit=settings.VIRTUAL_TOUR_SOFT_TIME_LIMIT + 60,
)
def generate_virtual_tour_task(property_id, job_id=None):
    """
    Génère la visite virtuelle d'un bien (worker Celery uniquement).
    Ne jamais appeler directement depuis une requête HTTP : passer par
    properties.video.service.request_virtual_tour().
    """
    from properties.video.pipeline import run_generation

    return run_generation(property_id, job_id)


@shared_task(name="properties.tasks.virtual_tour_healthcheck", ignore_result=False, soft_time_limit=60, time_limit=90)
def virtual_tour_healthcheck():
    """Diagnostic exécuté sur le worker (FFmpeg, codecs, stockage vidéo). Utilisé par verify_virtual_tour."""
    from properties.video.diagnostics import environment_report

    return environment_report()
