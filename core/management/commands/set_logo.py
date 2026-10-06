"""
Commande Django : python manage.py set_logo <chemin_image>

Copie le fichier image dans media/settings/ et enregistre la référence
dans SiteSettings (singleton), invalidant le cache automatiquement.
"""
import os
import shutil
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings as django_settings
from site_settings.models import SiteSettings


class Command(BaseCommand):
    help = "Définit le logo du site à partir d'un fichier image local"

    def add_arguments(self, parser):
        parser.add_argument("image_path", type=str, help="Chemin absolu vers l'image du logo")

    def handle(self, *args, **options):
        src = options["image_path"]
        if not os.path.isfile(src):
            raise CommandError(f"Fichier introuvable : {src}")

        # Destination dans MEDIA_ROOT/settings/
        filename = "logo_domiora" + os.path.splitext(src)[1].lower()
        dest_dir = os.path.join(django_settings.MEDIA_ROOT, "settings")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)

        shutil.copy2(src, dest)
        self.stdout.write(f"✅ Logo copié vers : {dest}")

        # Enregistrement en BDD (chemin relatif à MEDIA_ROOT)
        relative_path = os.path.join("settings", filename)
        s = SiteSettings.load()
        s.logo = relative_path
        s.save()

        self.stdout.write(self.style.SUCCESS(
            f"✅ Logo enregistré en base : {relative_path}"
        ))
