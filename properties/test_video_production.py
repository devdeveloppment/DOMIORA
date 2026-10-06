"""Tests de préparation au déploiement des visites virtuelles (Render, Redis, Cloudinary, vérification E2E)."""
import io
import os
import shutil
import tempfile
import threading
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import connection
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from properties.management.commands.verify_virtual_tour import Command
from properties.models import Property
from properties.test_video import FakeProvider, add_photos
from properties.video import checks, diagnostics, pipeline
from services.tests_property_search import make_owner, make_property

TMP_MEDIA = tempfile.mkdtemp(prefix="domiora_prod_media_")


class ProductionSettingsTests(SimpleTestCase):
    @override_settings(DEBUG=False, REDIS_URL="", CLOUDINARY_URL="", CELERY_TASK_ALWAYS_EAGER=True)
    def test_checks_warn_when_production_is_misconfigured(self):
        ids = {message.id for message in checks.virtual_tour_production_checks(None)}
        self.assertEqual(ids, {"domiora.W001", "domiora.W002", "domiora.W003"})

    @override_settings(DEBUG=False, REDIS_URL="redis://red:6379", CLOUDINARY_URL="cloudinary://k:s@demo", CELERY_TASK_ALWAYS_EAGER=False)
    def test_checks_pass_when_production_is_configured(self):
        self.assertEqual(checks.virtual_tour_production_checks(None), [])

    @override_settings(DEBUG=True, REDIS_URL="", CLOUDINARY_URL="")
    def test_no_production_warning_in_development(self):
        self.assertEqual(checks.virtual_tour_production_checks(None), [])

    def test_render_blueprint(self):
        """render.yaml (offre gratuite) : DEBUG=False, worker Celery dans le conteneur web, Redis gratuit,
        CLOUDINARY_URL déclarée sans valeur, aucune offre payante ni aucun secret."""
        from django.conf import settings

        with open(os.path.join(settings.BASE_DIR, "render.yaml"), encoding="utf-8") as handle:
            content = handle.read()
        with open(os.path.join(settings.BASE_DIR, "start.sh"), encoding="utf-8") as handle:
            start = handle.read()
        services = {}
        for block in content.split("\n  - type: ")[1:]:
            name = block.split("name: ", 1)[1].split("\n", 1)[0].strip()
            services[name] = block
        web = services["domiora"]
        self.assertIn('key: DEBUG\n        value: "False"', web)
        self.assertIn("key: CLOUDINARY_URL\n        sync: false", web)
        self.assertIn("key: REDIS_URL\n        fromService:\n          type: keyvalue\n          name: domiora-redis", web)
        self.assertIn("startCommand: bash start.sh", web)
        self.assertIn("celery -A config worker --pool=solo", start)
        self.assertIn("exec gunicorn config.wsgi:application", start)
        self.assertNotIn("domiora-worker", services)  # pas de Background Worker payant
        self.assertTrue(services["domiora-redis"].startswith("keyvalue"))
        plans = {line.split("plan:", 1)[1].strip() for line in content.splitlines() if line.strip().startswith("plan:")}
        self.assertEqual(plans, {"free"})
        self.assertNotIn("cloudinary://", content)
        self.assertNotIn("redis://", content)


class WorkerDiagnosticsTests(SimpleTestCase):
    def test_environment_report_detects_ffmpeg_and_codecs(self):
        report = diagnostics.environment_report()
        self.assertTrue(report["ffmpeg"])
        self.assertTrue(report["libx264"])
        self.assertTrue(report["xfade"])
        self.assertEqual(diagnostics.report_problems(report, production=False), [])
        self.assertNotIn("CLOUDINARY_URL", str(report))  # aucun secret

    def test_production_problems_are_reported(self):
        report = {"ffmpeg": "x", "libx264": True, "xfade": True, "debug": True, "broker": "filesystem",
                  "cloudinary_configured": False, "video_storage": "FileSystemStorage", "video_resource_type": "local"}
        problems = diagnostics.report_problems(report, production=True)
        self.assertEqual(len(problems), 4)


class CloudinaryUploadTests(SimpleTestCase):
    @patch.dict(os.environ, {"CLOUDINARY_URL": "cloudinary://key:secret@demo"})
    def test_video_is_uploaded_as_video_resource(self):
        from cloudinary_storage.storage import VideoMediaCloudinaryStorage

        storage = VideoMediaCloudinaryStorage()
        with patch("cloudinary.uploader.upload", return_value={"public_id": "media/properties/generated_tours/tour_x"}) as upload:
            name = storage.save("properties/generated_tours/tour.mp4", ContentFile(b"video", name="tour.mp4"))
        self.assertEqual(upload.call_args.kwargs["resource_type"], "video")
        self.assertEqual(name, "media/properties/generated_tours/tour_x")
        with patch("cloudinary.uploader.destroy", return_value={"result": "ok"}) as destroy:
            storage.delete(name)
        self.assertEqual(destroy.call_args.kwargs["resource_type"], "video")


@override_settings(MEDIA_ROOT=TMP_MEDIA, CELERY_TASK_ALWAYS_EAGER=False, DEBUG=True)
class VerifyCommandTests(TransactionTestCase):
    """Parcours complet avec un « worker » simulé dans un thread (génération réellement asynchrone)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.owner = make_owner("verify_owner")
        self.prop = make_property(self.owner, "Maison test", property_type=Property.PropertyType.MAISON_DE_VILLE)
        add_photos(self.prop, 3, size=(320, 180))
        self.queue = []

    def run_command(self, *args):
        # Le « worker » tourne dans un thread, en alternance stricte avec la commande
        # (SQLite en mémoire n'accepte pas d'écritures concurrentes) : chaque attente de la
        # commande laisse le worker avancer d'une scène, ce qui rend les états intermédiaires observables.
        go, back = threading.Semaphore(0), threading.Semaphore(0)

        def checkpoint(_index):
            back.release()
            go.acquire()

        provider = FakeProvider(on_scene=checkpoint)
        threads = []

        def worker(property_id, job_id):
            go.acquire()
            try:
                pipeline.run_generation(property_id, job_id)
            finally:
                connection.close()
                back.release()

        def enqueue(args=None, countdown=0):
            thread = threading.Thread(target=worker, args=args, daemon=True)
            threads.append(thread)
            thread.start()

        def wait_for_worker(_command, _seconds):
            go.release()
            back.acquire(timeout=10)

        out = io.StringIO()
        with patch("properties.tasks.generate_virtual_tour_task.apply_async", side_effect=enqueue), \
                patch("properties.video.pipeline.get_provider", return_value=provider), \
                patch("properties.video.ffmpeg.validate", return_value={}), \
                patch("properties.video.ffmpeg.probe", return_value={"codec": "h264", "duration": 20.0, "width": 1280, "height": 720}), \
                patch.object(Command, "sleep", wait_for_worker):
            try:
                call_command("verify_virtual_tour", "--skip-infra", "--poll", "0", "--timeout", "60", *args, stdout=out)
            except CommandError as error:
                return out.getvalue(), error
            finally:
                for thread in threads:
                    thread.join(timeout=30)
        return out.getvalue(), None

    def test_requires_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("verify_virtual_tour", "--skip-infra", "--property", str(self.prop.pk), stdout=io.StringIO())

    def test_end_to_end_and_regeneration(self):
        output, error = self.run_command("--property", str(self.prop.pk), "--yes")
        self.assertIsNone(error, output)
        self.assertIn("État : generating", output)  # états intermédiaires réellement observés
        self.assertIn("→ done", output)
        self.assertIn("La vidéo enregistrée correspond au job demandé", output)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_status, "done")

        output, error = self.run_command("--property", str(self.prop.pk), "--yes", "--regeneration")
        self.assertIsNone(error, output)
        self.assertIn("Ancienne vidéo masquée dès la demande de régénération", output)
        self.assertIn("La tâche obsolète n'a rien écrasé", output)
        self.prop.refresh_from_db()
        self.assertEqual(len([f for f in os.listdir(os.path.join(TMP_MEDIA, "properties", "generated_tours"))
                              if f.startswith(f"virtual_tour_prop_{self.prop.pk}_")]), 1)

    def test_failed_generation_is_reported(self):
        provider = FakeProvider(fail_with=RuntimeError("boom"))
        queue = self.queue
        out = io.StringIO()
        with patch("properties.tasks.generate_virtual_tour_task.apply_async", side_effect=lambda args=None, countdown=0: queue.append(args)), \
                patch("properties.video.pipeline.get_provider", return_value=provider), \
                patch.object(Command, "sleep", lambda _s, _t: [pipeline.run_generation(*queue.pop(0)) for _ in list(queue)]):
            with self.assertRaises(CommandError):
                call_command("verify_virtual_tour", "--skip-infra", "--poll", "0", "--property", str(self.prop.pk), "--yes", stdout=out)
        self.assertIn("Génération échouée (failed)", out.getvalue())
        self.assertIn(pipeline.MSG_GENERIC, out.getvalue())

    @override_settings(DEBUG=False, REDIS_URL="", CLOUDINARY_URL="")
    def test_configuration_failures_in_production(self):
        out = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("verify_virtual_tour", "--skip-infra", stdout=out)
        self.assertIn("REDIS_URL non défini", out.getvalue())
