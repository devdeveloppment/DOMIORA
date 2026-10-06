"""
Envoie le dossier media/ local vers Cloudinary sous LES MÊMES NOMS que ceux enregistrés en base,
afin que les références existantes (logo, photos, vidéos…) fonctionnent dès que CLOUDINARY_URL
est défini, sans modifier la base de données.

    python manage.py upload_media_to_cloudinary            → simulation (liste ce qui serait envoyé)
    python manage.py upload_media_to_cloudinary --yes      → envoi réel

Correspondance avec django-cloudinary-storage :
    nom en base "settings/logo.png"  →  URL .../image/upload/v1/media/settings/logo.png
    donc public_id "media/settings/logo" (sans extension), resource_type "image".
    Les vidéos (.mp4, .webm, .mov) sont envoyées en resource_type "video" (VideoMediaCloudinaryStorage).
Les fichiers déjà présents sur Cloudinary ne sont pas écrasés (sauf --overwrite).
Aucun secret n'est affiché.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "svg", "pdf", "tif", "tiff", "avif", "heic"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v", "ogg", "ogv"}
LARGE_FILE = 20 * 1024 * 1024


def cloudinary_target(relative_path):
    """Retourne (public_id, resource_type) pour un chemin relatif à MEDIA_ROOT, ou None si non pris en charge."""
    relative_path = relative_path.replace("\\", "/")
    base, dot, extension = relative_path.rpartition(".")
    extension = extension.lower() if dot else ""
    prefix = settings.MEDIA_URL.strip("/")
    if extension in IMAGE_EXTENSIONS:
        resource_type = "image"
    elif extension in VIDEO_EXTENSIONS:
        resource_type = "video"
    else:
        return None
    name = base if not base.startswith(prefix + "/") else base[len(prefix) + 1:]
    return f"{prefix}/{name}", resource_type


class Command(BaseCommand):
    help = "Envoie media/ vers Cloudinary sous les mêmes noms que ceux enregistrés en base."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Effectue réellement l'envoi (sinon simulation).")
        parser.add_argument("--overwrite", action="store_true", help="Remplace les fichiers déjà présents sur Cloudinary.")
        parser.add_argument("--exclude", action="append", default=[], help="Sous-dossier de media/ à ignorer (répétable).")

    def handle(self, *args, **options):
        if not getattr(settings, "CLOUDINARY_URL", None):
            raise CommandError("CLOUDINARY_URL n'est pas défini dans l'environnement de cette commande.")
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(secure=True)
        media_root = str(settings.MEDIA_ROOT)
        excluded = {e.strip("/\\") for e in options["exclude"]}
        planned, skipped = [], []
        for root, _dirs, files in os.walk(media_root):
            for filename in sorted(files):
                path = os.path.join(root, filename)
                relative = os.path.relpath(path, media_root).replace("\\", "/")
                if relative == ".gitkeep" or relative.split("/")[0] in excluded:
                    continue
                target = cloudinary_target(relative)
                if target is None:
                    skipped.append(relative)
                    continue
                planned.append((path, relative, *target))

        total = sum(os.path.getsize(p) for p, *_ in planned)
        mode = "ENVOI" if options["yes"] else "SIMULATION"
        self.stdout.write(f"{mode} : {len(planned)} fichier(s), {total / 1024 / 1024:.1f} Mo")
        for relative in skipped:
            self.stdout.write(self.style.WARNING(f"[IGNORÉ] format non pris en charge : {relative}"))

        uploaded = existing = failed = 0
        for path, relative, public_id, resource_type in planned:
            if not options["yes"]:
                self.stdout.write(f"[À ENVOYER] {relative} → {resource_type}/{public_id}")
                continue
            upload = cloudinary.uploader.upload_large if os.path.getsize(path) > LARGE_FILE else cloudinary.uploader.upload
            try:
                result = upload(
                    path, public_id=public_id, resource_type=resource_type,
                    overwrite=options["overwrite"], invalidate=options["overwrite"], tags=["media"],
                )
            except Exception as error:
                failed += 1
                self.stdout.write(self.style.ERROR(f"[ÉCHEC] {relative} ({type(error).__name__}: {str(error)[:120]})"))
                continue
            if result.get("existing"):
                existing += 1
                self.stdout.write(f"[DÉJÀ PRÉSENT] {relative}")
            else:
                uploaded += 1
                self.stdout.write(self.style.SUCCESS(f"[OK] {relative} → {resource_type}/{public_id}"))

        if options["yes"]:
            summary = f"{uploaded} envoyé(s), {existing} déjà présent(s), {failed} échec(s)"
            if failed:
                raise CommandError(summary)
            self.stdout.write(self.style.SUCCESS(f"Terminé : {summary}"))
        else:
            self.stdout.write("Simulation terminée. Relancez avec --yes pour envoyer.")
