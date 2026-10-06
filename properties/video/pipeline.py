"""
Pipeline de génération d'une visite virtuelle (exécuté par le worker Celery).

Toutes les écritures en base passent par un UPDATE filtré sur video_job_id :
une tâche obsolète (le propriétaire a relancé, supprimé ou réordonné des photos)
ne peut jamais écraser l'état ni la vidéo d'une génération plus récente.
On n'appelle jamais Property.save() ici (pas de notifications d'alertes parasites).
"""
import logging
import os
import shutil
import tempfile

import requests
from django.conf import settings
from django.core.files import File

from . import analysis, cards, ffmpeg, scenes
from .providers import get_provider

logger = logging.getLogger(__name__)

MSG_UNREADABLE = (
    "Certaines photos n'ont pas pu être lues. Vérifiez vos photos : au moins {min} photos lisibles sont nécessaires."
)
MSG_RENDER = "La génération de la vidéo a échoué. Vous pouvez relancer la génération ; si le problème persiste, contactez l'équipe DOMIORA."
MSG_TIMEOUT = "La génération a pris trop de temps. Réessayez plus tard ou réduisez le nombre de photos."
MSG_STORAGE = "La vidéo a été générée mais n'a pas pu être enregistrée. Réessayez dans quelques instants."
MSG_GENERIC = "Une erreur inattendue est survenue pendant la génération. Vous pouvez relancer la génération."


def min_photos_message(count):
    minimum = settings.VIRTUAL_TOUR_MIN_PHOTOS
    return (
        f"Ajoutez au moins {minimum} photos pour générer la visite virtuelle "
        f"(actuellement : {count} photo{'s' if count > 1 else ''})."
    )


class ObsoleteJob(Exception):
    """Une génération plus récente a été demandée."""


class GenerationFailure(Exception):
    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


def output_size():
    try:
        width, height = (int(v) for v in str(settings.VIRTUAL_TOUR_RESOLUTION).lower().split("x"))
    except (TypeError, ValueError):
        width, height = 1280, 720
    return width - width % 2, height - height % 2  # H.264 exige des dimensions paires


class Job:
    def __init__(self, property_id, job_id):
        self.property_id = property_id
        self.job_id = job_id

    def update(self, **fields):
        from properties.models import Property

        if not Property.objects.filter(pk=self.property_id, video_job_id=self.job_id).update(**fields):
            raise ObsoleteJob()

    def progress(self, status, percent):
        self.update(video_status=status, video_progress=max(0, min(100, int(percent))))

    def fail(self, message):
        from properties.models import Property

        try:
            self.update(video_status=Property.VideoStatus.FAILED, video_progress=0, video_error=message[:255])
        except ObsoleteJob:
            pass


def run_generation(property_id, job_id):
    """Génère la visite virtuelle. Retourne "done", "failed", "obsolete", "ignored" ou "missing"."""
    from celery.exceptions import SoftTimeLimitExceeded

    from properties.models import Property

    if not job_id:
        # Anciens messages en file (avant l'introduction de video_job_id) : ignorés.
        logger.info("Virtual tour task without job id ignored (property %s)", property_id)
        return "ignored"
    prop = Property.objects.filter(pk=property_id).first()
    if prop is None:
        return "missing"
    if prop.video_job_id != job_id:
        logger.info("Obsolete virtual tour job %s for property %s skipped", job_id, property_id)
        return "obsolete"

    job = Job(property_id, job_id)
    Status = Property.VideoStatus
    try:
        job.progress(Status.PREPARING, 2)
        minimum, maximum = settings.VIRTUAL_TOUR_MIN_PHOTOS, settings.VIRTUAL_TOUR_MAX_PHOTOS
        images = list(prop.images.order_by("order", "id")[:maximum])
        if len(images) < minimum:
            raise GenerationFailure(min_photos_message(len(images)))

        size, fps = output_size(), settings.VIRTUAL_TOUR_FPS
        with tempfile.TemporaryDirectory(prefix="domiora_tour_") as workdir:
            photos = []
            for index, image in enumerate(images):
                path = _download(image, workdir, index)
                if path:
                    try:
                        photos.append(analysis.read_photo_info(path))
                    except analysis.UnreadablePhoto as error:
                        logger.warning("Unreadable photo %s for property %s: %s", image.pk, property_id, error)
                job.progress(Status.PREPARING, 2 + 8 * (index + 1) / len(images))
            if len(photos) < minimum:
                raise GenerationFailure(MSG_UNREADABLE.format(min=minimum))

            texts = cards.card_texts(prop)
            cover = analysis.load_rgb(photos[0].path)
            cover.thumbnail((size[0] * 2, size[1] * 2))
            title_card = cards.render_title_card(texts, size, cover)
            outro_card = cards.render_outro_card(texts, size, cover)
            del cover

            storyboard = scenes.build_storyboard(photos, size, title_card, outro_card)
            provider = get_provider()
            clips = []
            for index, scene in enumerate(storyboard):
                clips.append(provider.render_scene(scene, index, workdir, size, fps))
                scene.image = None  # libère la carte dès qu'elle est rendue
                job.progress(Status.GENERATING, 10 + 75 * (index + 1) / len(storyboard))

            job.progress(Status.ASSEMBLING, 88)
            output = os.path.join(workdir, "tour.mp4")
            transitions = [scene.transition for scene in storyboard[1:]]
            duration = provider.assemble(clips, transitions, workdir, fps, output)
            music = getattr(settings, "VIRTUAL_TOUR_MUSIC_PATH", "")
            if music and os.path.isfile(music):
                output = ffmpeg.add_music(output, music, duration, os.path.join(workdir, "tour_music.mp4"))

            job.progress(Status.ASSEMBLING, 94)
            ffmpeg.validate(output, duration, size)
            job.progress(Status.ASSEMBLING, 97)
            _store(prop, job, output)
        logger.info("Virtual tour generated for property %s (job %s)", property_id, job_id)
        return "done"
    except ObsoleteJob:
        logger.info("Virtual tour job %s for property %s became obsolete", job_id, property_id)
        return "obsolete"
    except GenerationFailure as error:
        logger.warning("Virtual tour not generated for property %s: %s", property_id, error.user_message)
        job.fail(error.user_message)
    except SoftTimeLimitExceeded:
        logger.error("Virtual tour generation timed out for property %s", property_id)
        job.fail(MSG_TIMEOUT)
    except (ffmpeg.FFmpegUnavailable, ffmpeg.FFmpegError, ffmpeg.VideoValidationError):
        logger.exception("Virtual tour rendering failed for property %s", property_id)
        job.fail(MSG_RENDER)
    except Exception:
        logger.exception("Unexpected virtual tour failure for property %s", property_id)
        job.fail(MSG_GENERIC)
    return "failed"


def _download(image, workdir, index):
    """Copie locale d'une photo (une à la fois, en flux) ; None si elle est illisible."""
    extension = os.path.splitext(image.image.name)[1] or ".img"
    path = os.path.join(workdir, f"photo_{index:02d}{extension}")
    try:
        with image.image.storage.open(image.image.name, "rb") as source, open(path, "wb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
        return path
    except Exception as storage_error:
        url = image.image.url
        if url.startswith("/"):
            url = getattr(settings, "BASE_URL", "http://127.0.0.1:8000").rstrip("/") + url
        try:
            with requests.get(url, stream=True, timeout=20) as response:
                response.raise_for_status()
                with open(path, "wb") as target:
                    for chunk in response.iter_content(1024 * 1024):
                        target.write(chunk)
            return path
        except Exception as http_error:
            logger.warning("Photo %s unavailable (%s / %s)", image.pk, storage_error, http_error)
            return None


def _store(prop, job, output_path):
    """Enregistre la vidéo via le stockage du champ (Cloudinary vidéo ou local), puis publie le résultat."""
    from properties.models import Property

    field = Property._meta.get_field("virtual_tour_video")
    storage = field.storage
    name = f"{field.upload_to}virtual_tour_prop_{prop.pk}_{job.job_id[:8]}.mp4"
    try:
        with open(output_path, "rb") as handle:
            saved_name = storage.save(name, File(handle, name=os.path.basename(name)))
    except Exception as error:
        logger.exception("Virtual tour storage failed for property %s", prop.pk)
        raise GenerationFailure(MSG_STORAGE) from error

    previous = Property.objects.filter(pk=prop.pk).values_list("virtual_tour_video", flat=True).first()
    try:
        job.update(
            virtual_tour_video=saved_name,
            video_status=Property.VideoStatus.DONE,
            video_progress=100,
            video_error="",
        )
    except ObsoleteJob:
        _delete_quietly(storage, saved_name)
        raise
    if previous and previous != saved_name:
        _delete_quietly(storage, previous)


def _delete_quietly(storage, name):
    try:
        storage.delete(name)
    except Exception:
        logger.warning("Could not delete old virtual tour file %s", name)
