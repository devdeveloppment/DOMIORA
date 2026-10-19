import io
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import IdentityVerificationRequest, User

TMP = tempfile.mkdtemp(prefix="domiora-private-")
STORAGES = {**settings.STORAGES, "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def png():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, "PNG")
    return buf.getvalue()


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=f"{TMP}/public", PRIVATE_MEDIA_ROOT=f"{TMP}/private",
                   PRIVATE_MEDIA_BACKEND="filesystem")
class PrivateMediaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user("adm", password="x-Pass-123", role=User.Role.ADMIN)
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.client_user = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)

    def test_new_identity_documents_are_not_public(self):
        v = IdentityVerificationRequest.objects.create(owner=self.owner, id_document_front=ContentFile(png(), "r.png"),
                                                       id_document_back=ContentFile(png(), "v.png"))
        self.assertTrue((Path(TMP) / "private" / v.id_document_front.name).exists())
        self.assertFalse((Path(TMP) / "public" / v.id_document_front.name).exists())
        with self.assertRaises(Exception):
            v.id_document_front.url  # aucune URL publique
        url = reverse("dashboard:private_identity_document", args=[v.pk, "recto"])
        for user in (self.owner, self.client_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.admin)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Cache-Control"], "private, no-store")
        self.assertEqual(b"".join(resp.streaming_content), png())
        self.assertContains(self.client.get(reverse("dashboard:admin_identity_verification_detail", args=[v.pk])), url)

    def test_legacy_public_file_readable_then_migrated_idempotently(self):
        name = default_storage.save("id_documents/front/ancien.png", ContentFile(png()))
        v = IdentityVerificationRequest.objects.create(owner=self.owner, id_document_front=name, id_document_back=name)
        self.client.force_login(self.admin)
        url = reverse("dashboard:private_identity_document", args=[v.pk, "recto"])
        self.assertEqual(self.client.get(url).status_code, 200)  # repli sur l'ancien stockage
        out = io.StringIO()
        call_command("migrate_private_media", "--apply", "--manifest-dir", f"{TMP}/manifests", stdout=out)
        self.assertIn("'migrated': 1", out.getvalue())
        self.assertTrue(default_storage.exists(name))  # original conservé
        self.assertTrue((Path(TMP) / "private" / name).exists())
        out = io.StringIO()
        call_command("migrate_private_media", "--apply", "--manifest-dir", f"{TMP}/manifests", stdout=out)
        self.assertIn("'already_migrated': 2", out.getvalue())  # recto + verso pointent le même fichier
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_dry_run_copies_nothing_and_reports_missing(self):
        IdentityVerificationRequest.objects.create(owner=self.owner, id_document_front="id_documents/front/absent.png",
                                                   id_document_back="id_documents/back/absent.png")
        out = io.StringIO()
        call_command("migrate_private_media", "--manifest-dir", f"{TMP}/manifests", stdout=out)
        self.assertIn("'missing': 2", out.getvalue())
