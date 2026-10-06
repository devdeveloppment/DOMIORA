"""
Vérification de bout en bout de la génération des visites virtuelles après déploiement.

    python manage.py verify_virtual_tour
        → configuration, Redis, worker Celery, diagnostic exécuté SUR le worker (FFmpeg, Cloudinary)

    python manage.py verify_virtual_tour --property 42 --yes --base-url https://domiora.onrender.com
        → demande réelle → Redis → worker → FFmpeg → Cloudinary → fiche publique,
          avec suivi des états (pending, preparing, generating, assembling, done / failed)

    ... --regeneration
        → deux demandes successives : l'ancienne vidéo est masquée immédiatement,
          la tâche la plus ancienne devient obsolète et ne peut rien écraser.

Les étapes --property régénèrent réellement la vidéo du bien indiqué (action d'administration).
Aucune donnée privée ni aucun secret n'est affiché.
"""
import os
import tempfile
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from properties.video import diagnostics, ffmpeg
from properties.video.service import has_ready_video, request_virtual_tour

STATUS_ORDER = ["pending", "preparing", "generating", "assembling", "done"]


class Command(BaseCommand):
    help = "Vérifie la chaîne de génération des visites virtuelles (Redis, worker, FFmpeg, Cloudinary, fiche publique)."

    def add_arguments(self, parser):
        parser.add_argument("--property", type=int, help="Bien (id) sur lequel lancer une génération réelle de bout en bout.")
        parser.add_argument("--yes", action="store_true", help="Confirme la régénération réelle de la vidéo du bien.")
        parser.add_argument("--regeneration", action="store_true", help="Vérifie aussi le masquage et la protection contre les tâches obsolètes.")
        parser.add_argument("--base-url", default="", help="URL publique du site (ex. https://domiora.onrender.com) pour vérifier la fiche.")
        parser.add_argument("--timeout", type=int, default=900, help="Délai maximal d'attente d'une génération (secondes).")
        parser.add_argument("--poll", type=float, default=1.0, help="Intervalle de suivi des états (secondes).")
        parser.add_argument("--skip-infra", action="store_true", help="Ne pas contacter Redis ni le worker (diagnostic local).")

    # ------------------------------------------------------------------ sortie
    def ok(self, text):
        self.stdout.write(self.style.SUCCESS(f"[OK] {text}"))

    def warn(self, text):
        self.warnings += 1
        self.stdout.write(self.style.WARNING(f"[ATTENTION] {text}"))

    def fail(self, text):
        self.failures += 1
        self.stdout.write(self.style.ERROR(f"[ÉCHEC] {text}"))

    def info(self, text):
        self.stdout.write(f"[INFO] {text}")

    def sleep(self, seconds):
        time.sleep(seconds)

    # ------------------------------------------------------------------ commande
    def handle(self, *args, **options):
        self.failures = self.warnings = 0
        self.options = options
        self.production = not settings.DEBUG

        self.stdout.write(self.style.MIGRATE_HEADING("1. Configuration du service web"))
        self.check_configuration()
        if not options["skip_infra"]:
            self.stdout.write(self.style.MIGRATE_HEADING("2. Redis et worker Celery"))
            self.check_infrastructure()

        if options["property"]:
            if not options["yes"]:
                raise CommandError("La vérification de bout en bout régénère réellement la vidéo du bien : ajoutez --yes pour confirmer.")
            from properties.models import Property

            prop = Property.objects.filter(pk=options["property"]).first()
            if prop is None:
                raise CommandError(f"Bien {options['property']} introuvable.")
            self.stdout.write(self.style.MIGRATE_HEADING(f"3. Génération de bout en bout (bien {prop.pk})"))
            previous_url = self.end_to_end(prop)
            if options["regeneration"] and previous_url:
                self.stdout.write(self.style.MIGRATE_HEADING("4. Régénération et tâches obsolètes"))
                self.regeneration(prop, previous_url)

        summary = f"{self.failures} échec(s), {self.warnings} avertissement(s)"
        if self.failures:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(f"Terminé : {summary}"))

    # ------------------------------------------------------------------ 1
    def check_configuration(self):
        from properties.models import Property

        if self.production:
            self.ok("DEBUG=False")
        else:
            self.warn("DEBUG=True : mode développement (attendu False en production)")
        if getattr(settings, "REDIS_URL", ""):
            self.ok("REDIS_URL défini (broker Redis)")
        elif self.production:
            self.fail("REDIS_URL non défini : aucune vidéo ne sera générée en production")
        else:
            self.warn("Broker filesystem (développement local uniquement)")
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            (self.fail if self.production else self.warn)("CELERY_TASK_ALWAYS_EAGER actif (génération dans la requête HTTP)")
        storage = Property._meta.get_field("virtual_tour_video").storage
        resource_type = getattr(storage, "RESOURCE_TYPE", None)
        if getattr(settings, "CLOUDINARY_URL", None) and resource_type == "video":
            self.ok(f"Stockage vidéo : {type(storage).__name__} (resource_type=video)")
        elif self.production:
            self.fail(f"Stockage vidéo non durable : {type(storage).__name__} (CLOUDINARY_URL manquant ?)")
        else:
            self.warn(f"Stockage vidéo local : {type(storage).__name__} (développement)")

    # ------------------------------------------------------------------ 2
    def check_infrastructure(self):
        from config.celery import app

        redis_url = getattr(settings, "REDIS_URL", "")
        if redis_url:
            try:
                import redis

                redis.Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5).ping()
                self.ok("Redis répond (PING)")
            except Exception as error:
                self.fail(f"Redis injoignable ({type(error).__name__})")
                return

        try:
            replies = app.control.ping(timeout=5) or []
        except Exception as error:
            replies = []
            self.fail(f"Impossible d'interroger les workers ({type(error).__name__})")
        if replies:
            self.ok(f"{len(replies)} worker(s) Celery actif(s)")
            registered = app.control.inspect(timeout=5).registered() or {}
            names = {name for tasks in registered.values() for name in tasks}
            for task in ("properties.tasks.generate_virtual_tour_task", "properties.tasks.virtual_tour_healthcheck"):
                (self.ok if task in names else self.fail)(f"Tâche enregistrée sur le worker : {task}")
        else:
            self.fail("Aucun worker Celery ne répond (service domiora-worker démarré ?)")
            return

        if not redis_url:
            self.warn("Pas de backend de résultats : diagnostic du worker ignoré (broker local)")
            return
        from properties.tasks import virtual_tour_healthcheck

        try:
            report = virtual_tour_healthcheck.apply_async().get(timeout=90)
        except Exception as error:
            self.fail(f"Le diagnostic n'a pas été exécuté par le worker ({type(error).__name__})")
            return
        self.info(
            "Worker : {ffmpeg_version} | libx264={libx264} xfade={xfade} ffprobe={ffprobe} | "
            "stockage={video_storage} ({video_resource_type}) | DEBUG={debug} | {resolution}@{fps}".format(**report)
        )
        problems = diagnostics.report_problems(report, production=self.production)
        if problems:
            for problem in problems:
                self.fail(f"Worker : {problem}")
        else:
            self.ok("Environnement du worker prêt (FFmpeg, codecs, Redis, Cloudinary vidéo)")

    # ------------------------------------------------------------------ 3
    def wait_for(self, prop_id, job_id):
        from properties.models import Property

        seen, start = [], time.monotonic()
        while True:
            row = Property.objects.filter(pk=prop_id).values(
                "video_status", "video_progress", "video_error", "video_job_id", "virtual_tour_video"
            ).first()
            if row["video_job_id"] != job_id:
                return "superseded", seen, row
            if not seen or seen[-1] != row["video_status"]:
                seen.append(row["video_status"])
                self.info(f"État : {row['video_status']} ({row['video_progress']} %)")
            if row["video_status"] in ("done", "failed"):
                return row["video_status"], seen, row
            if time.monotonic() - start > self.options["timeout"]:
                return "timeout", seen, row
            self.sleep(self.options["poll"])

    def check_states(self, seen):
        known = [s for s in seen if s in STATUS_ORDER]
        positions = [STATUS_ORDER.index(s) for s in known]
        if positions == sorted(positions) and known and known[-1] == "done":
            missing = [s for s in STATUS_ORDER if s not in known]
            self.ok("États successifs : " + " → ".join(known))
            if missing:
                self.info("États trop brefs pour être observés à cet intervalle : " + ", ".join(missing))
        else:
            self.fail("Ordre des états inattendu : " + " → ".join(seen))

    def end_to_end(self, prop):
        """Retourne l'URL de la vidéo générée (ou None en cas d'échec)."""
        from properties.models import Property

        count = prop.images.count()
        if count < settings.VIRTUAL_TOUR_MIN_PHOTOS:
            self.fail(f"Le bien n'a que {count} photo(s) : {settings.VIRTUAL_TOUR_MIN_PHOTOS} minimum")
            return None
        old_url = prop.virtual_tour_video.url if has_ready_video(prop) else None

        queued, message = request_virtual_tour(prop)
        if not queued:
            self.fail(f"Demande refusée : {message}")
            return None
        job_id = prop.video_job_id
        self.ok(f"Génération mise en file (job {job_id[:8]})")
        prop.refresh_from_db()
        if not has_ready_video(prop):
            self.ok("Pendant la génération, la vidéo n'est plus présentée sur la fiche (statut ≠ done)")
        if old_url:
            self.check_public_page(prop, absent=old_url, label="ancienne vidéo masquée sur la fiche publique")

        outcome, seen, row = self.wait_for(prop.pk, job_id)
        if outcome == "failed":
            self.fail(f"Génération échouée (failed) : {row['video_error']}")
            return None
        if outcome != "done":
            self.fail(f"Génération non terminée : {outcome} (dernier état : {row['video_status']})")
            return None
        self.check_states(seen)

        prop = Property.objects.get(pk=prop.pk)
        url = prop.virtual_tour_video.url
        if job_id[:8] in prop.virtual_tour_video.name:
            self.ok("La vidéo enregistrée correspond au job demandé")
        else:
            self.fail("La vidéo enregistrée ne correspond pas au job demandé")
        self.check_video_url(prop, url)
        self.check_public_page(prop, present=url, label="vidéo affichée sur la fiche publique")
        return url

    def check_video_url(self, prop, url):
        if url.startswith("http"):
            if "/video/upload/" in url:
                self.ok("URL Cloudinary de type vidéo (/video/upload/)")
            else:
                self.fail(f"URL de stockage inattendue (pas /video/upload/) : {url}")
            try:
                with requests.get(url, stream=True, timeout=30) as response:
                    content_type = response.headers.get("Content-Type", "")
                    if response.status_code == 200 and content_type.startswith("video/"):
                        self.ok(f"Vidéo accessible ({content_type})")
                    else:
                        self.fail(f"Vidéo inaccessible : HTTP {response.status_code} {content_type}")
                        return
                    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
                        for chunk in response.iter_content(1024 * 1024):
                            handle.write(chunk)
                        local_path = handle.name
                self.probe(local_path)
                os.unlink(local_path)
            except requests.RequestException as error:
                self.fail(f"Vidéo inaccessible ({type(error).__name__})")
        else:
            storage = prop.virtual_tour_video.storage
            if storage.exists(prop.virtual_tour_video.name):
                self.ok(f"Fichier présent dans le stockage local ({url})")
                if hasattr(storage, "path"):
                    self.probe(storage.path(prop.virtual_tour_video.name))
            else:
                self.fail("Fichier vidéo absent du stockage")
            if self.production:
                self.fail("URL locale en production : Cloudinary n'est pas utilisé")

    def probe(self, path):
        try:
            info = ffmpeg.probe(path)
        except Exception as error:
            self.fail(f"Vidéo illisible ({type(error).__name__})")
            return
        if info["codec"] == "h264" and info["duration"] > 5:
            self.ok(f"Vidéo valide : h264 {info['width']}x{info['height']}, {info['duration']:.1f} s")
        else:
            self.fail(f"Vidéo inattendue : {info}")

    def check_public_page(self, prop, present=None, absent=None, label=""):
        base_url = self.options["base_url"].rstrip("/")
        if not base_url:
            self.info(f"Fiche publique non vérifiée (--base-url non fourni) : {label}")
            return
        from properties.views import _public_contactable_properties

        if not _public_contactable_properties().filter(pk=prop.pk).exists():
            self.warn(f"Bien non publié/validé : fiche publique non vérifiable ({label})")
            return
        try:
            html = requests.get(base_url + prop.get_absolute_url(), timeout=30).text
        except requests.RequestException as error:
            self.fail(f"Fiche publique inaccessible ({type(error).__name__})")
            return
        if present is not None:
            (self.ok if present in html else self.fail)(label)
        if absent is not None:
            (self.ok if absent not in html else self.fail)(label)

    # ------------------------------------------------------------------ 4
    def regeneration(self, prop, previous_url):
        from properties.models import Property

        request_virtual_tour(prop)
        older_job = prop.video_job_id
        request_virtual_tour(prop)
        newer_job = prop.video_job_id
        self.info(f"Deux demandes successives : {older_job[:8]} (ancienne) puis {newer_job[:8]} (récente)")
        prop.refresh_from_db()
        if not has_ready_video(prop):
            self.ok("Ancienne vidéo masquée dès la demande de régénération")
        else:
            self.fail("L'ancienne vidéo reste présentée pendant la régénération")
        self.check_public_page(prop, absent=previous_url, label="ancienne vidéo absente de la fiche pendant la régénération")

        outcome, seen, row = self.wait_for(prop.pk, newer_job)
        if outcome != "done":
            self.fail(f"Régénération non terminée : {outcome} {row.get('video_error', '')}")
            return
        self.check_states(seen)
        prop = Property.objects.get(pk=prop.pk)
        name = prop.virtual_tour_video.name
        if prop.video_job_id == newer_job and newer_job[:8] in name and older_job[:8] not in name:
            self.ok("La tâche obsolète n'a rien écrasé : seule la génération la plus récente est enregistrée")
        else:
            self.fail(f"Résultat inattendu après régénération : job={prop.video_job_id[:8]} fichier={name}")
        if previous_url.startswith("http"):
            try:
                status = requests.head(previous_url, timeout=20, allow_redirects=True).status_code
            except requests.RequestException:
                status = None
            if status == 404:
                self.ok("L'ancienne vidéo a été supprimée de Cloudinary")
            else:
                self.warn(f"L'ancienne URL répond encore (HTTP {status}) : cache CDN Cloudinary possible")
