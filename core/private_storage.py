"""
Stockage des fichiers SENSIBLES (pièces d'identité, preuves de terrain, documents de bien).

Ces fichiers ne doivent jamais avoir d'URL publique : ils sont servis uniquement par des
vues Django qui contrôlent les permissions (open_private()).

Backends (settings.PRIVATE_MEDIA_BACKEND) :
- "filesystem" (défaut sans Cloudinary) : PRIVATE_MEDIA_ROOT, dossier non servi par /media/.
- "cloudinary" (défaut si CLOUDINARY_URL) : ressources Cloudinary de type « authenticated »,
  lisibles seulement via une URL signée générée côté serveur. NON TESTÉ contre Cloudinary
  réel depuis cet environnement : à valider sur un compte de test avant production.

Les fichiers existants (avant migration) restent lisibles : open_private() retombe sur
l'ancien stockage public tant que `manage.py migrate_private_media` ne les a pas copiés.
"""
import posixpath

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage, default_storage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateCloudinaryStorage(Storage):
    def _public_id(self, name):
        return posixpath.splitext(name)[0]

    def _save(self, name, content):
        import cloudinary.uploader

        content.seek(0)
        result = cloudinary.uploader.upload(content, public_id=self._public_id(name), type="authenticated",
                                            resource_type="auto", overwrite=False, unique_filename=False)
        return f"{result['public_id']}.{result.get('format', posixpath.splitext(name)[1].lstrip('.'))}"

    def _signed_url(self, name):
        import cloudinary.utils

        public_id, ext = posixpath.splitext(name)
        return cloudinary.utils.private_download_url(public_id, ext.lstrip("."), type="authenticated")

    def _open(self, name, mode="rb"):
        import requests

        resp = requests.get(self._signed_url(name), timeout=20)
        resp.raise_for_status()
        return ContentFile(resp.content, name=name)

    def exists(self, name):
        try:
            import cloudinary.api

            cloudinary.api.resource(self._public_id(name), type="authenticated")
            return True
        except Exception:
            return False

    def url(self, name):
        raise NotImplementedError("Fichier privé : utiliser une vue protégée.")

    def size(self, name):
        return len(self._open(name).read())


def _build():
    backend = getattr(settings, "PRIVATE_MEDIA_BACKEND", "filesystem")
    if backend == "cloudinary":
        return PrivateCloudinaryStorage()
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


@deconstructible
class PrivateStorage(Storage):
    """Délègue au backend configuré au moment de chaque opération (pas figé au chargement)."""

    def _s(self):
        return _build()

    def _open(self, name, mode="rb"):
        return self._s().open(name, mode)

    def _save(self, name, content):
        return self._s().save(name, content)

    def exists(self, name):
        return self._s().exists(name)

    def delete(self, name):
        return self._s().delete(name)

    def size(self, name):
        return self._s().size(name)

    def get_available_name(self, name, max_length=None):
        return self._s().get_available_name(name, max_length=max_length)

    def url(self, name):
        raise NotImplementedError("Fichier privé : utiliser une vue protégée.")


_PRIVATE = PrivateStorage()


def private_storage():
    """Callable référencé par les champs (la migration ne fige pas le backend)."""
    return _PRIVATE


def open_private(fieldfile):
    """Ouvre un fichier sensible : stockage privé, sinon ancien stockage public (non migré)."""
    name = fieldfile.name
    storage = _build()
    if storage.exists(name):
        return storage.open(name, "rb")
    if default_storage.exists(name):
        return default_storage.open(name, "rb")
    raise FileNotFoundError(name)
