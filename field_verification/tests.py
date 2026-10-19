import io
import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import IdentityVerificationRequest, User
from payments.tests import make_property

from . import services
from .models import MissionEvidence, VerificationMission

SIMPLE_STATIC = {**settings.STORAGES,
                 "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                 "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
TMP_MEDIA = tempfile.mkdtemp(prefix="domiora-fv-")
S = VerificationMission.Status


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, "PNG")
    return buf.getvalue()


@override_settings(STORAGES=SIMPLE_STATIC, MEDIA_ROOT=TMP_MEDIA, PRIVATE_MEDIA_ROOT=TMP_MEDIA + "/private", PRIVATE_MEDIA_BACKEND="filesystem")
class MissionTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="x-Pass-123", role=User.Role.ADMIN)
        self.verifier = User.objects.create_user("verif", password="x-Pass-123", role=User.Role.VERIFIER)
        self.other_verifier = User.objects.create_user("verif2", password="x-Pass-123", role=User.Role.VERIFIER)
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.PENDING_DOCUMENTS)
        self.identity = IdentityVerificationRequest.objects.create(owner=self.owner, id_document_front="a.png",
                                                                   id_document_back="b.png")
        self.prop = make_property(self.owner, is_published=False, is_validated=False)
        self.mission = services.create_mission(self.admin, self.owner, self.prop, "Contrôler le titre", self.verifier)

    def _run_to_submission(self):
        services.start(self.verifier, self.mission)
        services.save_report(self.verifier, self.mission, {"identity_match": {"checked": True}}, "RAS", "Conforme.", "conform")
        services.submit_report(self.verifier, self.mission)

    def test_full_flow_admin_validates(self):
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.verification_status, User.VerificationStatus.PENDING_FIELD_VISIT)
        self._run_to_submission()
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.verification_status, User.VerificationStatus.FIELD_VISIT_COMPLETED)
        services.decide(self.admin, self.mission, "validate")
        self.owner.refresh_from_db()
        self.identity.refresh_from_db()
        self.assertEqual(self.owner.verification_status, User.VerificationStatus.APPROVED)
        self.assertEqual(self.identity.status, IdentityVerificationRequest.Status.APPROVED)
        self.assertEqual(self.mission.status, S.CLOSED)
        # La décision ne publie pas l'annonce.
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.is_published)
        self.assertTrue(self.mission.logs.filter(action="decision:validate").exists())

    def test_verifier_submission_never_approves(self):
        self._run_to_submission()
        self.owner.refresh_from_db()
        self.assertNotEqual(self.owner.verification_status, User.VerificationStatus.APPROVED)

    def test_verifier_cannot_decide(self):
        self._run_to_submission()
        with self.assertRaises(services.TransitionError):
            services.decide(self.verifier, self.mission, "validate")
        self.client.force_login(self.verifier)
        resp = self.client.post(reverse("dashboard:admin_mission_detail", args=[self.mission.pk]), {"action": "validate"})
        self.assertEqual(resp.status_code, 302)
        self.owner.refresh_from_db()
        self.assertNotEqual(self.owner.verification_status, User.VerificationStatus.APPROVED)

    def test_refuse_and_reverify_require_reason(self):
        self._run_to_submission()
        with self.assertRaises(services.TransitionError):
            services.decide(self.admin, self.mission, "refuse", "")
        services.decide(self.admin, self.mission, "reverify", "Photos floues")
        follow_up = VerificationMission.objects.get(previous_mission=self.mission)
        self.assertEqual(follow_up.status, S.TO_ASSIGN)

    def test_info_request_cycle(self):
        self._run_to_submission()
        services.request_info(self.admin, self.mission, "Photo de la façade")
        self.assertEqual(self.mission.status, S.INFO_REQUESTED)
        services.submit_report(self.verifier, self.mission)
        self.assertEqual(self.mission.status, S.REPORT_SUBMITTED)

    def test_invalid_transitions(self):
        with self.assertRaises(services.TransitionError):
            services.submit_report(self.verifier, self.mission)  # pas démarrée, rapport vide
        with self.assertRaises(services.TransitionError):
            services.decide(self.admin, self.mission, "validate")  # pas de rapport
        with self.assertRaises(services.TransitionError):
            services.assign(self.admin, self.mission, self.owner)  # pas un vérificateur

    def test_other_verifier_cannot_see_or_act(self):
        self.client.force_login(self.other_verifier)
        self.assertEqual(self.client.get(reverse("dashboard:verifier_mission", args=[self.mission.pk])).status_code, 404)
        resp = self.client.post(reverse("dashboard:verifier_mission", args=[self.mission.pk]), {"action": "start"})
        self.assertEqual(resp.status_code, 404)
        self.assertNotContains(self.client.get(reverse("dashboard:verifier_home")), "Contrôler le titre")

    def test_verifier_cannot_access_admin_or_owner_spaces(self):
        self.client.force_login(self.verifier)
        for name in ("dashboard:admin_missions", "dashboard:admin_overview", "dashboard:owner_overview",
                     "dashboard:client_overview"):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_non_verifier_cannot_open_verifier_space(self):
        for user in (self.owner, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("dashboard:verifier_home")).status_code, 302)

    def test_verifier_web_flow_with_evidence_and_gps(self):
        self.client.force_login(self.verifier)
        url = reverse("dashboard:verifier_mission", args=[self.mission.pk])
        self.assertContains(self.client.get(url), "Mission #")
        self.client.post(url, {"action": "start"})
        upload = SimpleUploadedFile("facade.png", png_bytes(), content_type="image/png")
        self.client.post(reverse("dashboard:verifier_evidence_upload", args=[self.mission.pk]), {
            "image": upload, "caption": "Façade", "latitude": "6.172500", "longitude": "1.231400",
            "accuracy": "12", "device_captured_at": "2026-10-19T10:00:00Z"})
        ev = MissionEvidence.objects.get(mission=self.mission)
        self.assertEqual(ev.location_source, "browser")
        self.assertEqual(str(ev.latitude), "6.172500")
        self.client.post(url, {"action": "submit", "report": "Bien conforme", "check_identity_match": "on"})
        self.mission.refresh_from_db()
        self.assertEqual(self.mission.status, S.REPORT_SUBMITTED)
        # Preuves : visibles par le vérificateur et l'admin, pas par le propriétaire ni un autre vérificateur.
        file_url = reverse("dashboard:mission_evidence_file", args=[ev.pk])
        self.assertEqual(self.client.get(file_url).status_code, 200)
        for user in (self.owner, self.other_verifier):
            self.client.force_login(user)
            self.assertEqual(self.client.get(file_url).status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(file_url).status_code, 200)

    def test_invalid_gps_ignored(self):
        services.start(self.verifier, self.mission)
        self.client.force_login(self.verifier)
        upload = SimpleUploadedFile("x.png", png_bytes(), content_type="image/png")
        self.client.post(reverse("dashboard:verifier_evidence_upload", args=[self.mission.pk]),
                         {"image": upload, "latitude": "999", "longitude": "abc"})
        ev = MissionEvidence.objects.get(mission=self.mission)
        self.assertIsNone(ev.latitude)
        self.assertEqual(ev.location_source, "none")

    def test_rejects_non_image_upload(self):
        services.start(self.verifier, self.mission)
        self.client.force_login(self.verifier)
        bad = SimpleUploadedFile("x.pdf", b"%PDF-1.4", content_type="application/pdf")
        self.client.post(reverse("dashboard:verifier_evidence_upload", args=[self.mission.pk]), {"image": bad})
        self.assertFalse(MissionEvidence.objects.exists())

    def test_admin_pages_render(self):
        self._run_to_submission()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("dashboard:admin_missions")), f"#{self.mission.pk}")
        self.assertContains(self.client.get(reverse("dashboard:admin_mission_detail", args=[self.mission.pk])), "Décision finale")
        resp = self.client.get(reverse("dashboard:admin_mission_create") + f"?owner={self.owner.pk}")
        self.assertContains(resp, "Créer la mission")
