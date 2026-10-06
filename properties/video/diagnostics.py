"""
Diagnostic de l'environnement de génération vidéo.

Exécuté sur le worker Celery (tâche virtual_tour_healthcheck) pour vérifier que
c'est bien LE WORKER qui dispose de FFmpeg et de Cloudinary, et non seulement le
service web. Ne renvoie aucun secret.
"""
import subprocess

from django.conf import settings


def environment_report():
    from properties.models import Property

    from . import ffmpeg

    report = {
        "debug": settings.DEBUG,
        "broker": "redis" if getattr(settings, "REDIS_URL", "") else "filesystem",
        "cloudinary_configured": bool(getattr(settings, "CLOUDINARY_URL", None)),
        "ffmpeg": None,
        "ffmpeg_version": "",
        "libx264": False,
        "xfade": False,
        "ffprobe": bool(ffmpeg.ffprobe_binary()),
        "resolution": settings.VIRTUAL_TOUR_RESOLUTION,
        "fps": settings.VIRTUAL_TOUR_FPS,
    }
    storage = Property._meta.get_field("virtual_tour_video").storage
    report["video_storage"] = type(storage).__name__
    report["video_resource_type"] = getattr(storage, "RESOURCE_TYPE", "local")
    try:
        binary = ffmpeg.ffmpeg_binary()
        report["ffmpeg"] = binary
        version = subprocess.run([binary, "-hide_banner", "-version"], capture_output=True, text=True, timeout=30).stdout
        report["ffmpeg_version"] = (version.splitlines() or [""])[0][:120]
        encoders = subprocess.run([binary, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
        filters = subprocess.run([binary, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30).stdout
        report["libx264"] = "libx264" in encoders
        report["xfade"] = " xfade " in filters
    except Exception as error:  # FFmpeg absent ou inutilisable
        report["ffmpeg_error"] = type(error).__name__
    return report


def report_problems(report, production):
    """Liste des problèmes bloquants détectés dans un rapport d'environnement."""
    problems = []
    if not report.get("ffmpeg"):
        problems.append("FFmpeg introuvable")
    if not report.get("libx264"):
        problems.append("Encodeur libx264 absent")
    if not report.get("xfade"):
        problems.append("Filtre xfade absent")
    if production:
        if report.get("debug"):
            problems.append("DEBUG est actif")
        if report.get("broker") != "redis":
            problems.append("Broker Redis non configuré (REDIS_URL)")
        if not report.get("cloudinary_configured"):
            problems.append("CLOUDINARY_URL non défini")
        if report.get("video_resource_type") != "video":
            problems.append(f"Stockage vidéo inattendu : {report.get('video_storage')} ({report.get('video_resource_type')})")
    return problems
