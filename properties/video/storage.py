"""Stockage des vidéos de visite virtuelle."""
from django.conf import settings


def video_storage():
    """
    Production : Cloudinary avec resource_type "video" (une vidéo n'est jamais envoyée comme image).
    Local : stockage par défaut du projet (disque, servi sous MEDIA_URL).
    Toujours utiliser FieldFile.url pour obtenir l'URL publique.
    """
    if getattr(settings, "CLOUDINARY_URL", None):
        from cloudinary_storage.storage import VideoMediaCloudinaryStorage

        return VideoMediaCloudinaryStorage()
    from django.core.files.storage import storages

    return storages["default"]
