"""
Point d'entrée unique pour demander une (re)génération de visite virtuelle.

Appelé uniquement depuis des vues dont l'appelant a déjà vérifié les droits
(propriétaire du bien ou administrateur). Ne publie ni ne valide jamais un bien.
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .pipeline import min_photos_message

logger = logging.getLogger(__name__)

MSG_QUEUED = "La visite virtuelle est en cours de préparation. Elle apparaîtra automatiquement une fois générée."
MSG_QUEUE_UNAVAILABLE = "Le service de génération vidéo est momentanément indisponible. Réessayez dans quelques minutes."
MSG_INTERRUPTED = (
    "La génération a été interrompue (redémarrage du serveur) et n'a pas pu reprendre. "
    "Cliquez sur « Relancer la génération »."
)


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
    fields = dict(video_status=Status.PENDING, video_progress=0, video_error="", video_job_id=job_id,
                  video_attempts=0, video_heartbeat_at=timezone.now())
    Property.objects.filter(pk=prop.pk).update(**fields)
    _apply(prop, fields)
    transaction.on_commit(lambda: enqueue(prop.pk, job_id, countdown))
    return True, MSG_QUEUED


def enqueue(property_id, job_id, countdown=0):
    """Met la tâche en file ; si le broker est indisponible, la génération passe en erreur (relance possible)."""
    from properties.models import Property
    from properties.tasks import generate_virtual_tour_task

    try:
        generate_virtual_tour_task.apply_async(args=[property_id, job_id], countdown=countdown)
        return True
    except Exception:
        logger.exception("Could not enqueue virtual tour generation for property %s", property_id)
        Property.objects.filter(pk=property_id, video_job_id=job_id).update(
            video_status=Property.VideoStatus.FAILED, video_error=MSG_QUEUE_UNAVAILABLE
        )
        return False


def is_stale(prop, now=None):
    """Génération « en cours » sans signe de vie depuis VIRTUAL_TOUR_STALE_SECONDS : processus interrompu."""
    if not (prop.video_job_id and in_progress(prop)):
        return False
    last = prop.video_heartbeat_at or prop.updated_at
    if last is None:
        return False
    return (now or timezone.now()) - last > timedelta(seconds=settings.VIRTUAL_TOUR_STALE_SECONDS)


def recover_stale(queryset=None, worker_starting=False):
    """
    Reprend les générations interrompues (serveur redémarré, processus tué faute de mémoire) :
    nouvelle tentative tant que VIRTUAL_TOUR_MAX_ATTEMPTS n'est pas atteint, sinon erreur explicite.
    Appelé au démarrage du worker et lors de la consultation du statut. Retourne le nombre repris.
    worker_starting=True : le worker (un seul processus) vient de démarrer, donc aucune génération ne
    tourne ; les étapes « en cours » sont forcément interrompues, quel que soit leur dernier signe de vie.
    """
    from properties.models import Property

    Status = Property.VideoStatus
    qs = queryset if queryset is not None else Property.objects.all()
    candidates = qs.exclude(video_job_id="").filter(
        video_status__in=[Status.PENDING, Status.PREPARING, Status.GENERATING, Status.ASSEMBLING]
    )
    now, resumed = timezone.now(), 0
    for prop in candidates:
        running_step = prop.video_status != Status.PENDING
        if not (is_stale(prop, now) or (worker_starting and running_step)):
            continue
        # UPDATE conditionnel : deux appels simultanés ne relancent pas deux fois la même génération.
        claim = Property.objects.filter(pk=prop.pk, video_job_id=prop.video_job_id, video_attempts=prop.video_attempts,
                                        video_status=prop.video_status)
        if prop.video_attempts + 1 >= settings.VIRTUAL_TOUR_MAX_ATTEMPTS:
            claim.update(video_status=Status.FAILED, video_progress=0, video_error=MSG_INTERRUPTED)
            logger.warning("Virtual tour of property %s interrupted too many times: marked as failed", prop.pk)
            continue
        if claim.update(video_status=Status.PENDING, video_progress=0, video_attempts=prop.video_attempts + 1,
                        video_heartbeat_at=now):
            logger.info("Resuming interrupted virtual tour of property %s (attempt %s)", prop.pk, prop.video_attempts + 2)
            enqueue(prop.pk, prop.video_job_id)
            resumed += 1
    return resumed


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
    ready = has_ready_video(prop)
    return {
        "status": prop.video_status,
        "label": status_label(prop),
        "progress": prop.video_progress if not ready else 100,
        "error": prop.video_error,
        "in_progress": in_progress(prop),
        "video_url": prop.virtual_tour_video.url if ready else None,
        "photo_count": prop.images.count(),
        "min_photos": settings.VIRTUAL_TOUR_MIN_PHOTOS,
        "max_photos": settings.VIRTUAL_TOUR_MAX_PHOTOS,
    }


def status_label(prop):
    """Quatre états lisibles : En attente, En cours, Terminé, Erreur (les étapes internes restent en base)."""
    Status = _status()
    if prop.video_status == Status.DONE:
        return "Terminé" if prop.virtual_tour_video else "Erreur"
    if prop.video_status == Status.FAILED:
        return "Erreur"
    if prop.video_status == Status.PENDING:
        if not prop.video_job_id:
            return "Non générée"
        return "En attente" + (" (nouvelle tentative)" if prop.video_attempts else "")
    return "En cours"


def _apply(prop, fields):
    for key, value in fields.items():
        setattr(prop, key, value)
