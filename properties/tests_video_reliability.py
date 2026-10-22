"""
Fiabilité des visites virtuelles : ressources FFmpeg bornées, nouvelles tentatives limitées,
reprise des générations interrompues, anti doublon, statuts lisibles et pages sans N+1.
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from properties.models import Property
from properties.video import ffmpeg, pipeline, service

from services.tests_property_search import SIMPLE_STATIC

from .test_video import FakeProvider, VideoFixture, add_photos, image_file

Status = Property.VideoStatus


class FFmpegResourceTests(VideoFixture):
    @override_settings(VIRTUAL_TOUR_FFMPEG_THREADS=1, VIRTUAL_TOUR_FINAL_PRESET="veryfast", VIRTUAL_TOUR_ASSEMBLY_CHUNK=3)
    def test_commands_limit_threads_and_use_fast_preset(self):
        calls = []
        with patch("properties.video.ffmpeg._run", side_effect=lambda args, timeout=600: calls.append(args) or ""), \
                patch("properties.video.ffmpeg.ffmpeg_binary", return_value="ffmpeg"):
            clips = [(f"c{i}.mp4", 4.0) for i in range(7)]
            ffmpeg.assemble(clips, ["fade"] * 6, 0.6, 24, "/tmp", "out.mp4")
        self.assertTrue(all("-threads" in args and args[args.index("-threads") + 1] == "1" for args in calls))
        final = calls[-1]
        self.assertEqual(final[final.index("-preset") + 1], "veryfast")
        # assemblage par blocs de 3 au plus : jamais plus de 3 entrées décodées en même temps
        self.assertTrue(all(args.count("-i") <= 3 for args in calls))

    @override_settings(VIRTUAL_TOUR_FFMPEG_THREADS=0)
    def test_zero_threads_means_automatic(self):
        self.assertEqual(ffmpeg.thread_args(), [])

    def test_killed_process_is_transient(self):
        class Done:
            returncode = -9

        with patch("subprocess.run", return_value=Done()):
            with self.assertRaises(ffmpeg.FFmpegError) as raised:
                ffmpeg._run(["ffmpeg"])
        self.assertTrue(raised.exception.transient)

    def test_ordinary_failure_is_not_transient(self):
        class Done:
            returncode = 1

        with patch("subprocess.run", return_value=Done()):
            with self.assertRaises(ffmpeg.FFmpegError) as raised:
                ffmpeg._run(["ffmpeg"])
        self.assertFalse(raised.exception.transient)


@override_settings(VIRTUAL_TOUR_MAX_ATTEMPTS=3)
class RetryTests(VideoFixture):
    def setUp(self):
        super().setUp()
        add_photos(self.prop, 3)

    def test_transient_error_schedules_a_limited_retry(self):
        job = self.start_job()
        with patch("properties.video.service.enqueue") as enqueue:
            result = self.run_with(FakeProvider(fail_with=ffmpeg.FFmpegError("killed", transient=True)), job=job)
        self.assertEqual(result, "retry")
        self.assertEqual((self.prop.video_status, self.prop.video_attempts, self.prop.video_job_id), (Status.PENDING, 1, job))
        enqueue.assert_called_once_with(self.prop.pk, job, countdown=30)

    def test_retries_stop_at_the_limit(self):
        job = self.start_job()
        Property.objects.filter(pk=self.prop.pk).update(video_attempts=2)
        with patch("properties.video.service.enqueue") as enqueue:
            result = self.run_with(FakeProvider(fail_with=ffmpeg.FFmpegError("killed", transient=True)), job=job)
        self.assertEqual(result, "failed")
        self.assertEqual(self.prop.video_status, Status.FAILED)
        self.assertEqual(self.prop.video_error, pipeline.MSG_RENDER)
        enqueue.assert_not_called()

    def test_permanent_error_is_not_retried(self):
        with patch("properties.video.service.enqueue") as enqueue:
            result = self.run_with(FakeProvider(fail_with=ffmpeg.FFmpegError("bad filter")))
        self.assertEqual(result, "failed")
        enqueue.assert_not_called()

    def test_duplicate_delivery_of_a_finished_job_is_ignored(self):
        job = self.start_job()
        Property.objects.filter(pk=self.prop.pk).update(video_status=Status.DONE, virtual_tour_video="x.mp4")
        provider = FakeProvider()
        self.assertEqual(self.run_with(provider, job=job), "duplicate")
        self.assertEqual(provider.scenes, [])

    def test_heartbeat_is_written_during_generation(self):
        job = self.start_job()
        Property.objects.filter(pk=self.prop.pk).update(video_heartbeat_at=None)
        self.run_with(FakeProvider(), job=job)
        self.assertIsNotNone(self.prop.video_heartbeat_at)
        self.assertEqual(self.prop.video_status, Status.DONE)


@override_settings(VIRTUAL_TOUR_MAX_ATTEMPTS=3, VIRTUAL_TOUR_STALE_SECONDS=600)
class StaleRecoveryTests(VideoFixture):
    def stuck(self, status=Status.ASSEMBLING, minutes=30, attempts=0):
        job = uuid.uuid4().hex
        Property.objects.filter(pk=self.prop.pk).update(
            video_job_id=job, video_status=status, video_progress=88, video_attempts=attempts,
            video_heartbeat_at=timezone.now() - timedelta(minutes=minutes),
        )
        return job

    def test_stuck_generation_is_resumed(self):
        job = self.stuck()
        with patch("properties.video.service.enqueue") as enqueue:
            self.assertEqual(service.recover_stale(), 1)
        self.prop.refresh_from_db()
        self.assertEqual((self.prop.video_status, self.prop.video_progress, self.prop.video_attempts), (Status.PENDING, 0, 1))
        enqueue.assert_called_once_with(self.prop.pk, job)

    def test_repeated_interruptions_end_in_a_clear_error(self):
        self.stuck(attempts=2)
        with patch("properties.video.service.enqueue") as enqueue:
            service.recover_stale()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_status, Status.FAILED)
        self.assertEqual(self.prop.video_error, service.MSG_INTERRUPTED)
        enqueue.assert_not_called()

    def test_active_generation_is_left_alone(self):
        self.stuck(minutes=1)
        with patch("properties.video.service.enqueue") as enqueue:
            self.assertEqual(service.recover_stale(), 0)
        enqueue.assert_not_called()

    def test_worker_start_resumes_running_steps_but_not_queued_jobs(self):
        self.stuck(minutes=1)
        other = Property.objects.create(owner=self.owner, title="Autre bien", price=1000, city="Lomé",
                                        video_job_id="q" * 32, video_status=Status.PENDING, video_heartbeat_at=timezone.now())
        with patch("properties.video.service.enqueue") as enqueue:
            self.assertEqual(service.recover_stale(worker_starting=True), 1)
        enqueue.assert_called_once()
        other.refresh_from_db()
        self.assertEqual(other.video_attempts, 0)

    def test_status_endpoint_recovers_and_is_never_cached(self):
        self.stuck()
        self.client.force_login(self.owner)
        with patch("properties.video.service.enqueue"):
            resp = self.client.get(reverse("dashboard:owner_property_video_status", args=[self.prop.pk]))
        self.assertEqual(resp["Cache-Control"], "no-store")
        self.assertEqual(resp.json()["status"], Status.PENDING)
        self.assertEqual(resp.json()["label"], "En attente (nouvelle tentative)")


@override_settings(STORAGES=SIMPLE_STATIC)
class StatusAndPermissionTests(VideoFixture):
    def test_four_readable_states(self):
        p = self.prop
        cases = [
            (dict(video_status=Status.PENDING, video_job_id=""), "Non générée"),
            (dict(video_status=Status.PENDING, video_job_id="j"), "En attente"),
            (dict(video_status=Status.GENERATING, video_job_id="j"), "En cours"),
            (dict(video_status=Status.ASSEMBLING, video_job_id="j"), "En cours"),
            (dict(video_status=Status.DONE, virtual_tour_video="v.mp4"), "Terminé"),
            (dict(video_status=Status.DONE, virtual_tour_video=""), "Erreur"),
            (dict(video_status=Status.FAILED), "Erreur"),
        ]
        for fields, label in cases:
            for key, value in fields.items():
                setattr(p, key, value)
            self.assertEqual(p.video_label, label, fields)

    def test_relaunch_while_running_does_not_create_a_duplicate_job(self):
        add_photos(self.prop, 3)
        job = uuid.uuid4().hex
        Property.objects.filter(pk=self.prop.pk).update(video_job_id=job, video_status=Status.GENERATING,
                                                        video_heartbeat_at=timezone.now())
        self.client.force_login(self.owner)
        with patch("properties.video.service.enqueue") as enqueue:
            self.client.post(reverse("dashboard:owner_property_video_generate", args=[self.prop.pk]))
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.video_job_id, job)
        enqueue.assert_not_called()

    def test_failed_generation_can_be_relaunched_by_its_owner_only(self):
        add_photos(self.prop, 3)
        Property.objects.filter(pk=self.prop.pk).update(video_job_id="old", video_status=Status.FAILED)
        url = reverse("dashboard:owner_property_video_generate", args=[self.prop.pk])
        self.client.force_login(self.other_owner)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.owner)
        with patch("properties.video.service.enqueue") as enqueue, self.captureOnCommitCallbacks(execute=True):
            self.client.post(url)
        self.prop.refresh_from_db()
        self.assertEqual((self.prop.video_status, self.prop.video_attempts), (Status.PENDING, 0))
        self.assertNotEqual(self.prop.video_job_id, "old")
        enqueue.assert_called_once()

    def test_public_page_never_shows_an_unfinished_or_failed_video(self):
        for status in (Status.GENERATING, Status.FAILED):
            Property.objects.filter(pk=self.prop.pk).update(video_status=status, virtual_tour_video="properties/generated_tours/x.mp4")
            body = self.client.get(self.prop.get_absolute_url()).content.decode()
            self.assertNotIn("generated_tours/x.mp4", body, status)


@override_settings(STORAGES=SIMPLE_STATIC)
class FastSubmissionTests(VideoFixture):
    def test_creation_only_queues_the_video_after_commit(self):
        from accounts.models import User

        User.objects.filter(pk=self.owner.pk).update(verification_status=User.VerificationStatus.APPROVED)
        self.client.force_login(self.owner)
        data = {"title": "Maison neuve à Baguida", "property_type": "villa", "transaction_type": "location",
                "price": "90000", "currency": "XOF", "country": "Togo", "city": "Lomé", "bedrooms": "2",
                "bathrooms": "1", "surface_area": "70", "floors": "1", "status": "disponible",
                "images": [image_file(f"i{i}.jpg") for i in range(3)]}
        with patch("properties.video.pipeline.run_generation") as generation, \
                patch("properties.video.service.enqueue") as enqueue, \
                self.captureOnCommitCallbacks(execute=True) as callbacks:
            resp = self.client.post(reverse("dashboard:owner_property_create"), data)
        self.assertEqual(resp.status_code, 302)
        generation.assert_not_called()  # aucune vidéo calculée pendant la requête HTTP
        prop = Property.objects.get(title="Maison neuve à Baguida")
        self.assertEqual(prop.images.count(), 3)  # images enregistrées avant la mise en file
        self.assertTrue(callbacks)
        enqueue.assert_called_once_with(prop.pk, prop.video_job_id, 0)
        self.assertEqual(prop.video_status, Status.PENDING)


@override_settings(STORAGES=SIMPLE_STATIC)
class OwnerListQueryTests(VideoFixture):
    def test_property_list_query_count_does_not_grow_with_listings(self):
        self.client.force_login(self.owner)
        add_photos(self.prop, 2)

        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(reverse("dashboard:owner_properties")).status_code, 200)
            return len(ctx.captured_queries)

        count()  # premier appel : création des réglages du site
        before = count()
        for i in range(4):
            extra = Property.objects.create(owner=self.owner, title=f"Bien {i}", price=1000, city="Lomé")
            add_photos(extra, 2, start=10 * i)
        self.assertEqual(count(), before)
