"""
Copie les fichiers sensibles existants de l'ancien stockage public vers le stockage privé.

- Simulation par défaut ; --apply pour copier ; --limit N pour un échantillon.
- Idempotent : un fichier déjà présent dans le stockage privé avec la même empreinte SHA-256
  est ignoré.
- Vérifie chaque copie (taille + SHA-256 relus depuis le stockage privé) et le type MIME
  (en-tête image réel via Pillow pour les champs image).
- Ne supprime JAMAIS les originaux (le nettoyage exigera une autorisation explicite).
- Écrit un manifeste JSON (domiora_backups/) : statut par fichier, pour audit et reprise.
- Ne modifie aucune ligne de la base : les champs gardent le même nom de fichier.
"""
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from core.private_storage import private_storage

FIELDS = [
    ("accounts", "User", "id_document", True),
    ("accounts", "IdentityVerificationRequest", "id_document_front", True),
    ("accounts", "IdentityVerificationRequest", "id_document_back", True),
    ("field_verification", "MissionEvidence", "image", True),
    ("properties", "PropertyDocument", "file", False),
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def image_ok(data):
    from PIL import Image

    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


class Command(BaseCommand):
    help = "Copie (sans suppression) les fichiers sensibles vers le stockage privé."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=0, help="Nombre maximum de fichiers à copier (échantillon).")
        parser.add_argument("--manifest-dir", default=str(Path(settings.BASE_DIR).parent / "domiora_backups"))

    def handle(self, *args, apply=False, limit=0, manifest_dir=None, **options):
        from django.apps import apps

        private = private_storage()
        report, seen_hashes, copied = [], {}, 0
        for app, model_name, field, is_image in FIELDS:
            model = apps.get_model(app, model_name)
            for obj in model.objects.exclude(**{field: ""}).exclude(**{f"{field}__isnull": True}).iterator():
                name = getattr(obj, field).name
                entry = {"model": f"{app}.{model_name}", "pk": obj.pk, "field": field, "name": name}
                report.append(entry)
                if not default_storage.exists(name):
                    entry["status"] = "private_only" if private.exists(name) else "missing"
                    continue
                with default_storage.open(name, "rb") as fh:
                    data = fh.read()
                digest = sha256(data)
                entry.update(size=len(data), sha256=digest)
                if digest in seen_hashes:
                    entry["duplicate_of"] = seen_hashes[digest]
                seen_hashes.setdefault(digest, f"{app}.{model_name}#{obj.pk}.{field}")
                if is_image and not image_ok(data):
                    entry["status"] = "invalid_image"
                    continue
                if private.exists(name):
                    with private.open(name, "rb") as fh:
                        entry["status"] = "already_migrated" if sha256(fh.read()) == digest else "conflict"
                    continue
                if not apply or (limit and copied >= limit):
                    entry["status"] = "to_migrate"
                    continue
                saved = private.save(name, ContentFile(data))
                with private.open(saved, "rb") as fh:
                    check = fh.read()
                entry["status"] = "migrated" if saved == name and sha256(check) == digest else "verify_failed"
                entry["saved_as"] = saved
                copied += 1

        summary = {}
        for e in report:
            summary[e.get("status")] = summary.get(e.get("status"), 0) + 1
        dups = sum(1 for e in report if "duplicate_of" in e)
        self.stdout.write(f"Fichiers sensibles : {len(report)} · {summary} · doublons : {dups}")
        Path(manifest_dir).mkdir(parents=True, exist_ok=True)
        path = Path(manifest_dir) / f"private_media_manifest_{datetime.now():%Y%m%d_%H%M%S}_{'apply' if apply else 'dryrun'}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(f"Manifeste : {path}")
        if not apply:
            self.stdout.write("Simulation : aucune copie. Originaux jamais supprimés par cette commande.")
