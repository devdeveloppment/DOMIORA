"""Tests du bloc A : visite virtuelle (pipeline, statuts, stockage, permissions)."""
import io
import os
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from properties.models import Property, PropertyImage
from properties.video import analysis, cards, ffmpeg, pipeline, scenes, service
from properties.video.storage import video_storage
from services.tests_property_search import SIMPLE_STATIC, make_owner, make_property

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp(prefix="domiora_test_media_")


def image_file(name, size=(800, 450), color=(120, 80, 60)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def add_photos(prop, count, size=(800, 450), start=0):
    return [
        PropertyImage.objects.create(property=prop, image=image_file(f"p{start + i}.jpg", size, (40 + i * 9 % 200, 90, 140)), order=start + i)
        for i in range(count)
    ]


def ffmpeg_available():
    try:
        ffmpeg.ffmpeg_binary()
        return True
    except ffmpeg.FFmpegUnavailable:
        return False


class FakeProvider:
    """Fournisseur simulé : enregistre les scènes sans lancer FFmpeg."""

    def __init__(self, on_scene=None, fail_with=None):
        self.scenes, self.pixels, self.on_scene, self.fail_with = [], [], on_scene, fail_with

    def render_scene(self, scene, index, workdir, output_size, fps):
        if self.fail_with:
            raise self.fail_with
        self.scenes.append(scene)
        if scene.kind == "photo":
            with Image.open(scene.source) as img:
                self.pixels.append(img.convert("RGB").getpixel((5, 5)))
        if self.on_scene:
            self.on_scene(index)
        return os.path.join(workdir, f"s{index}.mp4"), scene.duration

    def assemble(self, clips, transitions, workdir, fps, out_path):
        with open(out_path, "wb") as handle:
            handle.write(b"fake-mp4")
        return scenes.expected_duration(self.scenes) if self.scenes else 1.0


@override_settings(MEDIA_ROOT=TMP_MEDIA, CELERY_TASK_ALWAYS_EAGER=False)
class VideoFixture(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.owner = make_owner(f"owner_{uuid.uuid4().hex[:6]}")
        self.other_owner = make_owner(f"other_{uuid.uuid4().hex[:6]}")
        self.client_user = User.objects.create_user(username=f"cli_{uuid.uuid4().hex[:6]}", password="x-test-pass-123", role=User.Role.CLIENT)
        self.admin = User.objects.create_user(username=f"adm_{uuid.uuid4().hex[:6]}", password="x-test-pass-123", role=User.Role.ADMIN)
        self.prop = make_property(
            self.owner, "Villa lumineuse 250 000 FCFA tél 90 12 34 56 contact@prive.tg",
            property_type=Property.PropertyType.VILLA, neighborhood="Tokoin", address="12 rue Secrète",
            price=250_000,
        )

    def start_job(self, prop=None):
        prop = prop or self.prop
        job = uuid.uuid4().hex
        Property.objects.filter(pk=prop.pk).update(video_job_id=job, video_status=Property.VideoStatus.PENDING)
        return job

    def run_with(self, provider, prop=None, job=None):
        prop = prop or self.prop
        job = job or self.start_job(prop)
        with patch("properties.video.pipeline.get_provider", return_value=provider), \
                patch("properties.video.ffmpeg.validate", return_value={}):
            result = pipeline.run_generation(prop.pk, job)
        prop.refresh_from_db()
        return result


# ---------------------------------------------------------------------------
# Analyse, storyboard, cartes
# ---------------------------------------------------------------------------
class AnalysisAndStoryboardTests(TestCase):
    def info(self, w, h):
        return analysis.PhotoInfo(path="x.jpg", width=w, height=h)

    def test_orientation_based_motions(self):
        size = (1280, 720)
        self.assertEqual(analysis.choose_motion(self.info(1600, 900), 0, size), analysis.ESTABLISHING)
        self.assertEqual(analysis.choose_motion(self.info(900, 1600), 0, size), analysis.PORTRAIT)
        self.assertEqual(analysis.choose_motion(self.info(900, 1600), 3, size), analysis.PORTRAIT)
        self.assertIn(analysis.choose_motion(self.info(4000, 1000), 2, size), (analysis.PAN_LEFT, analysis.PAN_RIGHT))
        self.assertEqual(analysis.choose_motion(self.info(1200, 1000), 2, size), analysis.TILT_DOWN)
        landscape = [analysis.choose_motion(self.info(1920, 1080), i, size) for i in range(1, 5)]
        self.assertEqual(len(set(landscape)), 4)  # pas le même mouvement partout

    def test_low_resolution_photo_is_not_zoomed(self):
        motion = analysis.choose_motion(self.info(640, 360), 4, (1280, 720))
        self.assertIn(motion, (analysis.PAN_LEFT, analysis.PAN_RIGHT))

    def test_storyboard_structure_and_duration(self):
        photos = [self.info(1600, 900) for _ in range(5)]
        board = scenes.build_storyboard(photos, (1280, 720))
        self.assertEqual([s.kind for s in board], ["title"] + ["photo"] * 5 + ["outro"])
        self.assertEqual(board[-1].transition, "fadeblack")
        self.assertGreater(len({s.transition for s in board[2:-1]}), 1)  # transitions variées
        self.assertAlmostEqual(scenes.expected_duration(board), sum(s.duration for s in board) - 0.6 * 6)

    def test_duration_adapts_to_photo_count_with_cap(self):
        self.assertGreater(scenes.photo_duration(3), scenes.photo_duration(20))
        twenty = scenes.build_storyboard([self.info(1600, 900) for _ in range(20)], (1280, 720))
        self.assertLess(scenes.expected_duration(twenty), 75)

    def test_frames_stay_inside_photo(self):
        for motion in (analysis.ZOOM_IN, analysis.ZOOM_OUT, analysis.PAN_LEFT, analysis.PAN_RIGHT, analysis.TILT_DOWN, analysis.ESTABLISHING):
            for x, y, w, h in scenes._windows(motion, (1500, 900), (1280, 720), 20):
                self.assertGreaterEqual(x, -1e-6)
                self.assertGreaterEqual(y, -1e-6)
                self.assertLessEqual(x + w, 1500 + 1e-6)
                self.assertLessEqual(y + h, 900 + 1e-6)


class CardTextTests(TestCase):
    def test_sanitize_removes_price_phone_email_and_links(self):
        text = cards.sanitize_card_text("Villa 4 ch. 250 000 FCFA, tél: +228 90 12 34 56, info@prive.tg www.x.com prix négociable")
        for forbidden in ("250", "FCFA", "90 12", "@", "www", "prix"):
            self.assertNotIn(forbidden.lower(), text.lower())
        self.assertIn("Villa 4 ch.", text)

    def test_card_texts_contain_only_allowed_public_fields(self):
        owner = make_owner("card_owner")
        prop = make_property(owner, "Appartement Tokoin 150k par mois 99887766", neighborhood="Tokoin",
                             address="12 rue Secrète", price=150_000)
        texts = cards.card_texts(prop)
        joined = " ".join(texts.values())
        self.assertIn("Appartement", joined)
        self.assertIn("Lomé", joined)
        self.assertIn("Tokoin", joined)
        for forbidden in ("rue Secrète", "150", "99887766", "+22890001122", "@prive.example", "par mois"):
            self.assertNotIn(forbidden, joined)

    def test_cards_render(self):
        texts = {"title": "Maison à Lomé", "subtitle": "Villa · Lomé — Bè"}
        self.assertEqual(cards.render_title_card(texts, (320, 180)).size, (320, 180))
        self.assertEqual(cards.render_outro_card(texts, (320, 180), Image.new("RGB", (400, 300))).size, (320, 180))


# ---------------------------------------------------------------------------
# Service : demande de génération
# ---------------------------------------------------------------------------
class RequestVirtualTourTests(VideoFixture):
    def test_one_photo_does_not_start_ffmpeg(self):
        add_photos(self.prop, 1)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            queued, message = service.request_virtual_tour(self.prop)
        self.assertFalse(queued)
        self.assertIn("au moins 3 photos", message)
        apply_async.assert_not_called()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_status, Property.VideoStatus.PENDING)
        self.assertEqual(self.prop.video_error, message)

    def test_three_photos_are_queued_after_commit(self):
        add_photos(self.prop, 3)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            queued, _ = service.request_virtual_tour(self.prop)
        self.assertTrue(queued)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.video_job_id)
        apply_async.assert_called_once_with(args=[self.prop.pk, self.prop.video_job_id], countdown=0)

    def test_broker_unavailable_marks_failed_without_breaking_request(self):
        add_photos(self.prop, 3)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async", side_effect=ConnectionError("redis down")), \
                self.captureOnCommitCallbacks(execute=True):
            service.request_virtual_tour(self.prop)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_status, Property.VideoStatus.FAILED)
        self.assertEqual(self.prop.video_error, service.MSG_QUEUE_UNAVAILABLE)

    def test_dropping_below_minimum_removes_existing_video(self):
        add_photos(self.prop, 2)
        self.prop.virtual_tour_video.save("old.mp4", ContentFile(b"old"), save=False)
        Property.objects.filter(pk=self.prop.pk).update(virtual_tour_video=self.prop.virtual_tour_video.name, video_status="done")
        path = self.prop.virtual_tour_video.path
        self.prop.refresh_from_db()
        service.request_virtual_tour(self.prop)
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.virtual_tour_video)
        self.assertFalse(os.path.exists(path))
        self.assertNotEqual(self.prop.video_status, Property.VideoStatus.DONE)


# ---------------------------------------------------------------------------
# Pipeline (fournisseur simulé)
# ---------------------------------------------------------------------------
class PipelineTests(VideoFixture):
    def test_statuses_progress_and_storage(self):
        add_photos(self.prop, 3)
        seen = []

        def on_scene(index):
            self.prop.refresh_from_db()
            seen.append((self.prop.video_status, self.prop.video_progress))

        result = self.run_with(FakeProvider(on_scene=on_scene))
        self.assertEqual(result, "done")
        self.assertEqual(seen[0][0], Property.VideoStatus.PREPARING)  # pendant la 1re scène
        self.assertEqual(seen[-1][0], Property.VideoStatus.GENERATING)
        progress = [p for _, p in seen]
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(self.prop.video_status, Property.VideoStatus.DONE)
        self.assertEqual(self.prop.video_progress, 100)
        self.assertEqual(self.prop.video_error, "")
        self.assertTrue(os.path.exists(self.prop.virtual_tour_video.path))
        self.assertTrue(self.prop.virtual_tour_video.url.startswith("/media/properties/generated_tours/"))

    def test_owner_order_is_respected(self):
        photos = add_photos(self.prop, 4)
        for image, order in zip(photos, [3, 1, 0, 2]):
            PropertyImage.objects.filter(pk=image.pk).update(order=order)
        provider = FakeProvider()
        self.run_with(provider)
        expected = [photos[2], photos[1], photos[3], photos[0]]
        reference = []
        for image in expected:
            with Image.open(image.image.path) as img:
                reference.append(img.convert("RGB").getpixel((5, 5)))
        self.assertEqual(provider.pixels, reference)

    def test_more_than_twenty_photos_uses_first_twenty(self):
        add_photos(self.prop, 22, size=(320, 180))
        provider = FakeProvider()
        self.run_with(provider)
        self.assertEqual(len([s for s in provider.scenes if s.kind == "photo"]), 20)

    def test_twenty_photos(self):
        add_photos(self.prop, 20, size=(320, 180))
        provider = FakeProvider()
        self.assertEqual(self.run_with(provider), "done")
        self.assertEqual(len(provider.scenes), 22)

    def test_portrait_and_landscape_motions(self):
        add_photos(self.prop, 2, size=(800, 450))
        add_photos(self.prop, 1, size=(450, 800), start=2)
        provider = FakeProvider()
        self.run_with(provider)
        motions = [s.motion for s in provider.scenes if s.kind == "photo"]
        self.assertEqual(motions[0], analysis.ESTABLISHING)
        self.assertEqual(motions[2], analysis.PORTRAIT)

    def test_ffmpeg_failure_sets_user_friendly_error(self):
        add_photos(self.prop, 3)
        result = self.run_with(FakeProvider(fail_with=ffmpeg.FFmpegError("x264 [error]: broken pipe at 0x7f")))
        self.assertEqual(result, "failed")
        self.assertEqual(self.prop.video_status, Property.VideoStatus.FAILED)
        self.assertEqual(self.prop.video_error, pipeline.MSG_RENDER)
        self.assertNotIn("x264", self.prop.video_error)

    def test_timeout_sets_error(self):
        add_photos(self.prop, 3)
        self.run_with(FakeProvider(fail_with=SoftTimeLimitExceeded()))
        self.assertEqual(self.prop.video_error, pipeline.MSG_TIMEOUT)

    def test_unreadable_photos(self):
        add_photos(self.prop, 3)
        for image in self.prop.images.all()[:2]:
            with open(image.image.path, "wb") as handle:
                handle.write(b"not an image")
        self.run_with(FakeProvider())
        self.assertEqual(self.prop.video_status, Property.VideoStatus.FAILED)
        self.assertIn("n'ont pas pu être lues", self.prop.video_error)

    def test_obsolete_job_is_skipped(self):
        add_photos(self.prop, 3)
        old_job = self.start_job()
        self.start_job()  # nouvelle demande
        provider = FakeProvider()
        with patch("properties.video.pipeline.get_provider", return_value=provider):
            self.assertEqual(pipeline.run_generation(self.prop.pk, old_job), "obsolete")
        self.assertEqual(provider.scenes, [])

    def test_job_made_obsolete_during_rendering_never_overwrites(self):
        add_photos(self.prop, 3)
        newer = uuid.uuid4().hex

        def supersede(index):
            if index == 1:
                Property.objects.filter(pk=self.prop.pk).update(video_job_id=newer, video_status="pending", video_progress=0)

        result = self.run_with(FakeProvider(on_scene=supersede))
        self.assertEqual(result, "obsolete")
        self.assertEqual(self.prop.video_job_id, newer)
        self.assertEqual(self.prop.video_status, Property.VideoStatus.PENDING)
        self.assertFalse(self.prop.virtual_tour_video)
        generated = os.path.join(TMP_MEDIA, "properties", "generated_tours")
        self.assertFalse(os.path.isdir(generated) and any(f"prop_{self.prop.pk}_" in f for f in os.listdir(generated)))

    def test_obsolete_after_storage_deletes_new_file(self):
        add_photos(self.prop, 3)
        job = self.start_job()
        original_update = pipeline.Job.update

        def update(job_self, **fields):
            if fields.get("video_status") == Property.VideoStatus.DONE:
                Property.objects.filter(pk=self.prop.pk).update(video_job_id="newer")
            return original_update(job_self, **fields)

        with patch.object(pipeline.Job, "update", update):
            self.assertEqual(self.run_with(FakeProvider(), job=job), "obsolete")
        generated = os.path.join(TMP_MEDIA, "properties", "generated_tours")
        self.assertFalse(any(job[:8] in f for f in os.listdir(generated)) if os.path.isdir(generated) else False)

    def test_legacy_message_without_job_id_is_ignored(self):
        self.assertEqual(pipeline.run_generation(self.prop.pk, None), "ignored")

    def test_regeneration_replaces_previous_file(self):
        add_photos(self.prop, 3)
        self.run_with(FakeProvider())
        first_path = self.prop.virtual_tour_video.path
        self.run_with(FakeProvider())
        self.assertNotEqual(self.prop.virtual_tour_video.path, first_path)
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.exists(self.prop.virtual_tour_video.path))

    def test_validation_failure_is_reported(self):
        add_photos(self.prop, 3)
        job = self.start_job()
        with patch("properties.video.pipeline.get_provider", return_value=FakeProvider()), \
                patch("properties.video.ffmpeg.validate", side_effect=ffmpeg.VideoValidationError("Durée inattendue")):
            self.assertEqual(pipeline.run_generation(self.prop.pk, job), "failed")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_error, pipeline.MSG_RENDER)


# ---------------------------------------------------------------------------
# Stockage
# ---------------------------------------------------------------------------
class StorageTests(TestCase):
    @override_settings(CLOUDINARY_URL="")
    def test_local_storage_without_cloudinary(self):
        from django.core.files.storage import FileSystemStorage

        self.assertIsInstance(video_storage(), FileSystemStorage)

    @override_settings(CLOUDINARY_URL="cloudinary://key:secret@demo")
    @patch.dict(os.environ, {"CLOUDINARY_URL": "cloudinary://key:secret@demo"})
    def test_cloudinary_uses_video_resource_type(self):
        import cloudinary
        from cloudinary_storage.storage import VideoMediaCloudinaryStorage

        # L'instanciation réelle lit la configuration Cloudinary du serveur : on la neutralise ici.
        with patch.object(VideoMediaCloudinaryStorage, "__init__", return_value=None):
            storage = video_storage()
        self.assertIsInstance(storage, VideoMediaCloudinaryStorage)
        self.assertEqual(storage._get_resource_type("tour.mp4"), "video")
        previous = cloudinary.config().cloud_name
        cloudinary.config(cloud_name="demo")
        try:
            # Même construction d'URL que VideoMediaCloudinaryStorage._get_url
            url = cloudinary.CloudinaryResource("media/tour.mp4", default_resource_type=storage._get_resource_type("tour.mp4")).url
        finally:
            cloudinary.config(cloud_name=previous)
        self.assertIn("/video/upload/", url)
        self.assertNotIn("/image/upload/", url)

    def test_fields_use_dynamic_video_storage(self):
        for name in ("virtual_tour_video", "uploaded_tour_video"):
            self.assertIs(Property._meta.get_field(name)._storage_callable, video_storage)


@override_settings(MEDIA_ROOT=TMP_MEDIA, STORAGES=SIMPLE_STATIC)
class PublicPlayerTests(VideoFixture):
    def test_detail_page_uses_storage_url(self):
        self.prop.virtual_tour_video.save("tour_ok.mp4", ContentFile(b"video"), save=False)
        Property.objects.filter(pk=self.prop.pk).update(virtual_tour_video=self.prop.virtual_tour_video.name, video_status="done")
        self.prop.refresh_from_db()
        response = self.client.get(self.prop.get_absolute_url())
        self.assertContains(response, f'src="{self.prop.virtual_tour_video.url}"')
        self.assertNotContains(response, 'src="/media/{{')

    def test_video_hidden_while_regenerating(self):
        self.prop.virtual_tour_video.save("tour_old.mp4", ContentFile(b"video"), save=False)
        Property.objects.filter(pk=self.prop.pk).update(virtual_tour_video=self.prop.virtual_tour_video.name, video_status="generating")
        self.prop.refresh_from_db()
        response = self.client.get(self.prop.get_absolute_url())
        self.assertNotContains(response, self.prop.virtual_tour_video.url)


# ---------------------------------------------------------------------------
# Permissions, photos, administration
# ---------------------------------------------------------------------------
@override_settings(MEDIA_ROOT=TMP_MEDIA)
class OwnerRoutesTests(VideoFixture):
    def urls(self, prop=None):
        prop = prop or self.prop
        return {
            "generate": reverse("dashboard:owner_property_video_generate", args=[prop.pk]),
            "status": reverse("dashboard:owner_property_video_status", args=[prop.pk]),
        }

    def test_owner_can_generate_and_follow_status(self):
        add_photos(self.prop, 3)
        self.client.force_login(self.owner)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.urls()["generate"])
        self.assertEqual(response.status_code, 302)
        apply_async.assert_called_once()
        data = self.client.get(self.urls()["status"]).json()
        self.assertEqual(data["status"], "pending")
        self.assertTrue(data["in_progress"])
        self.assertEqual(data["photo_count"], 3)
        self.assertNotIn("prive", str(data))

    def test_generate_requires_post(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.urls()["generate"]).status_code, 405)

    def test_other_owner_is_refused(self):
        add_photos(self.prop, 3)
        self.client.force_login(self.other_owner)
        for name, url in self.urls().items():
            response = self.client.post(url) if name == "generate" else self.client.get(url)
            self.assertEqual(response.status_code, 404, name)
        image = self.prop.images.first()
        move = reverse("dashboard:owner_property_image_move", args=[self.prop.pk, image.pk])
        self.assertEqual(self.client.post(move, {"direction": "down"}).status_code, 404)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_job_id, "")

    def test_client_and_visitor_are_refused(self):
        add_photos(self.prop, 3)
        image = self.prop.images.first()
        move = reverse("dashboard:owner_property_image_move", args=[self.prop.pk, image.pk])
        for user in (self.client_user, None):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in (self.urls()["generate"], move):
                response = self.client.post(url, {"direction": "down"})
                self.assertEqual(response.status_code, 302)
                self.assertNotIn("proprietaire/biens", response["Location"])
            response = self.client.get(self.urls()["status"])
            self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_job_id, "")
        self.assertEqual([i.order for i in self.prop.images.order_by("order")], [0, 1, 2])

    def test_reorder_swaps_photos_and_regenerates_existing_video(self):
        photos = add_photos(self.prop, 3)
        Property.objects.filter(pk=self.prop.pk).update(video_status="done", virtual_tour_video="properties/generated_tours/x.mp4")
        self.client.force_login(self.owner)
        url = reverse("dashboard:owner_property_image_move", args=[self.prop.pk, photos[0].pk])
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"direction": "down"})
        ordered = list(self.prop.images.order_by("order").values_list("pk", flat=True))
        self.assertEqual(ordered, [photos[1].pk, photos[0].pk, photos[2].pk])
        apply_async.assert_called_once()
        self.assertEqual(apply_async.call_args.kwargs["countdown"], 10)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_status, Property.VideoStatus.PENDING)  # ancienne vidéo masquée

    def test_deleting_photo_regenerates_video(self):
        photos = add_photos(self.prop, 4)
        Property.objects.filter(pk=self.prop.pk).update(video_status="done", virtual_tour_video="properties/generated_tours/y.mp4")
        self.client.force_login(self.owner)
        url = reverse("dashboard:owner_property_image_delete", args=[self.prop.pk, photos[1].pk])
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url)
        apply_async.assert_called_once()
        self.prop.refresh_from_db()
        self.assertNotEqual(self.prop.video_status, Property.VideoStatus.DONE)

    def test_deleting_photo_below_minimum_removes_video(self):
        photos = add_photos(self.prop, 3)
        Property.objects.filter(pk=self.prop.pk).update(video_status="done", virtual_tour_video="properties/generated_tours/z.mp4")
        self.client.force_login(self.owner)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async:
            self.client.post(reverse("dashboard:owner_property_image_delete", args=[self.prop.pk, photos[0].pk]))
        apply_async.assert_not_called()
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.virtual_tour_video)
        self.assertIn("au moins 3 photos", self.prop.video_error)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class AdminValidationTests(VideoFixture):
    def setUp(self):
        super().setUp()
        Property.objects.filter(pk=self.prop.pk).update(is_validated=False, is_published=False, validation_status="pending")

    def test_validation_enqueues_without_synchronous_rendering(self):
        add_photos(self.prop, 3)
        self.client.force_login(self.admin)
        with patch("properties.video.pipeline.run_generation") as run_generation, \
                patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("dashboard:admin_property_validate", args=[self.prop.pk]))
        run_generation.assert_not_called()
        apply_async.assert_called_once()
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_validated and self.prop.is_published)

    def test_validation_does_not_depend_on_photos(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:admin_property_validate", args=[self.prop.pk]))
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_validated)
        self.assertIn("au moins 3 photos", self.prop.video_error)

    def test_ready_video_is_not_regenerated_on_validation(self):
        add_photos(self.prop, 3)
        Property.objects.filter(pk=self.prop.pk).update(video_status="done", virtual_tour_video="properties/generated_tours/ok.mp4")
        self.client.force_login(self.admin)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async:
            self.client.post(reverse("dashboard:admin_property_validate", args=[self.prop.pk]))
        apply_async.assert_not_called()

    def test_admin_can_regenerate_but_owner_cannot_use_admin_route(self):
        add_photos(self.prop, 3)
        url = reverse("dashboard:admin_property_video_generate", args=[self.prop.pk])
        self.client.force_login(self.owner)
        self.client.post(url)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_job_id, "")
        self.client.force_login(self.admin)
        with patch("properties.tasks.generate_virtual_tour_task.apply_async") as apply_async, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url)
        apply_async.assert_called_once()
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.is_published)  # générer une vidéo ne publie rien


# ---------------------------------------------------------------------------
# Intégration FFmpeg réelle (petite résolution)
# ---------------------------------------------------------------------------
@unittest.skipUnless(ffmpeg_available(), "FFmpeg indisponible")
@override_settings(MEDIA_ROOT=TMP_MEDIA, VIRTUAL_TOUR_RESOLUTION="320x180", VIRTUAL_TOUR_FPS=8)
class FFmpegIntegrationTests(VideoFixture):
    def test_real_generation_three_photos_with_ffprobe_validation(self):
        add_photos(self.prop, 2, size=(640, 360))
        add_photos(self.prop, 1, size=(360, 640), start=2)
        job = self.start_job()
        self.assertEqual(pipeline.run_generation(self.prop.pk, job), "done")
        self.prop.refresh_from_db()
        info = ffmpeg.probe(self.prop.virtual_tour_video.path)
        self.assertEqual((info["width"], info["height"], info["codec"]), (320, 180, "h264"))
        self.assertGreater(info["duration"], 15)

    def test_chunked_assembly_with_many_scenes(self):
        add_photos(self.prop, 7, size=(480, 270))  # 9 scènes : assemblage en plusieurs blocs
        job = self.start_job()
        self.assertEqual(pipeline.run_generation(self.prop.pk, job), "done")
        self.prop.refresh_from_db()
        photos = [analysis.PhotoInfo("x", 480, 270)] * 7
        expected = scenes.expected_duration(scenes.build_storyboard(photos, (320, 180)))
        self.assertAlmostEqual(ffmpeg.probe(self.prop.virtual_tour_video.path)["duration"], expected, delta=1.0)

    def test_validation_rejects_corrupt_file(self):
        path = os.path.join(TMP_MEDIA, "corrupt.mp4")
        with open(path, "wb") as handle:
            handle.write(os.urandom(5000))
        with self.assertRaises(ffmpeg.VideoValidationError):
            ffmpeg.validate(path, 10, (320, 180))

    def test_validation_rejects_missing_file(self):
        with self.assertRaises(ffmpeg.VideoValidationError):
            ffmpeg.validate(os.path.join(TMP_MEDIA, "absent.mp4"), 10, (320, 180))
