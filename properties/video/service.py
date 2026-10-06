"""
Point d'entrée unique pour demander une (re)génération de visite virtuelle.

Appelé uniquement depuis des vues dont l'appelant a déjà vérifié les droits
(propriétaire du bien ou administrateur). Ne publie ni ne valide jamais un bien.
"""
import logging
import uuid

from django.conf import settings
from django.db import transaction

from .pipeline import min_photos_message

logger = logging.getLogger(__name__)

MSG_QUEUED = "La visite virtuelle est en cours de préparation. Elle apparaîtra automatiquement une fois générée."
MSG_QUEUE_UNAVAILABLE = "Le service de génération vidéo est momentanément indisponible. Réessayez dans quelques minutes."


def _status():
    from properties.models import Property

    return Property.VideoStatus


def in_progress(prop):
    Status = _status()
    return prop.video_status in (Status.PREPARING, Status.GENERATING, Status.ASSEMBLING) or (
        prop.video_status == Status.PENDING and bool(prop.video_job_id)
    )


def has_ready_video(prop):
    return prop.video_status == _status().DONE and bool(prop.virtual_tour_video)


def request_virtual_tour(prop, countdown=0):
    """
    Demande une génération asynchrone. Retourne (mise_en_file: bool, message pour l'utilisateur).

    - Moins de VIRTUAL_TOUR_MIN_PHOTOS photos : pas de FFmpeg ; la vidéo existante (qui ne
      correspondrait plus aux photos) est retirée et un message invite à ajouter des photos.
    - Sinon : nouveau video_job_id (toute tâche antérieure devient obsolète), puis mise en file
      après le commit de la transaction.
    """
    from properties.models import Property
    from properties.tasks import generate_virtual_tour_task

    Status = Property.VideoStatus
    count = prop.images.count()
    if count < settings.VIRTUAL_TOUR_MIN_PHOTOS:
        message = min_photos_message(count)
        discard_video(prop)
        fields = dict(video_status=Status.PENDING, video_progress=0, video_error=message, video_job_id="", virtual_tour_video="")
        Property.objects.filter(pk=prop.pk).update(**fields)
        _apply(prop, fields)
        return False, message

    job_id = uuid.uuid4().hex
    fields = dict(video_status=Status.PENDING, video_progress=0, video_error="", video_job_id=job_id)
    Property.objects.filter(pk=prop.pk).update(**fields)
    _apply(prop, fields)

    def enqueue():
        try:
            generate_virtual_tour_task.apply_async(args=[prop.pk, job_id], countdown=countdown)
        except Exception:
            logger.exception("Could not enqueue virtual tour generation for property %s", prop.pk)
            Property.objects.filter(pk=prop.pk, video_job_id=job_id).update(
                video_status=Status.FAILED, video_error=MSG_QUEUE_UNAVAILABLE
            )

    transaction.on_commit(enqueue)
    return True, MSG_QUEUED


def discard_video(prop):
    """Supprime le fichier vidéo généré (s'il existe) sans toucher au reste du bien."""
    name = prop.virtual_tour_video.name if prop.virtual_tour_video else ""
    if not name:
        return
    try:
        prop.virtual_tour_video.storage.delete(name)
    except Exception:
        logger.warning("Could not delete virtual tour file %s", name)


def status_payload(prop):
    """État de la visite virtuelle pour l'interface propriétaire (aucune donnée privée)."""
    Status = _status()
    labels = {
        Status.PENDING: "En attente",
        Status.PREPARING: "Préparation",
        Status.GENERATING: "Génération en cours",
        Status.ASSEMBLING: "Assemblage",
        Status.DONE: "Terminé",
        Status.FAILED: "Erreur",
    }
    ready = has_ready_video(prop)
    return {
        "status": prop.video_status,
        "label": labels.get(prop.video_status, prop.video_status),
        "progress": prop.video_progress if not ready else 100,
        "error": prop.video_error,
        "in_progress": in_progress(prop),
        "video_url": prop.virtual_tour_video.url if ready else None,
        "photo_count": prop.images.count(),
        "min_photos": settings.VIRTUAL_TOUR_MIN_PHOTOS,
        "max_photos": settings.VIRTUAL_TOUR_MAX_PHOTOS,
    }


def _apply(prop, fields):
    for key, value in fields.items():
        setattr(prop, key, value)
