"""Tests de la migration des médias locaux vers Cloudinary (mêmes noms qu'en base)."""
import io
import os
import shutil
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from properties.management.commands.upload_media_to_cloudinary import cloudinary_target

TMP_MEDIA = tempfile.mkdtemp(prefix="domiora_media_upload_")


class TargetMappingTests(SimpleTestCase):
    def test_public_ids_match_storage_urls(self):
        """Le public_id envoyé doit correspondre à l'URL que django-cloudinary-storage produira pour le nom en base."""
        import cloudinary

        previous = cloudinary.config().cloud_name
        cloudinary.config(cloud_name="demo")
        try:
            for name, expected_type in [
                ("settings/ChatGPT_Image_21_juin_2026_17_00_44_HDvMlo8.png", "image"),
                ("properties/2026/08/photo.webp", "image"),
                ("properties/generated_tours/virtual_tour_prop_1_ab.mp4", "video"),
                ("id_documents/cni.jpg", "image"),
            ]:
                public_id, resource_type = cloudinary_target(name)
                self.assertEqual(resource_type, expected_type)
                storage_url = cloudinary.CloudinaryResource("media/" + name, default_resource_type=resource_type).url
                extension = name.rsplit(".", 1)[1]
                self.assertTrue(storage_url.endswith(f"/{resource_type}/upload/v1/{public_id}.{extension}"), storage_url)
        finally:
            cloudinary.config(cloud_name=previous)

    def test_unsupported_and_prefixed_names(self):
        self.assertIsNone(cloudinary_target("docs/contrat.docx"))
        self.assertEqual(cloudinary_target("media/settings/logo.png"), ("media/settings/logo", "image"))


@override_settings(MEDIA_ROOT=TMP_MEDIA, CLOUDINARY_URL="cloudinary://key:secret@demo")
class UploadCommandTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for relative, size in [("settings/logo.png", 10), ("properties/2026/08/a.webp", 10),
                               ("properties/generated_tours/v.mp4", 10), ("id_documents/cni.jpg", 10),
                               ("docs/notes.txt", 5), (".gitkeep", 0)]:
            path = os.path.join(TMP_MEDIA, *relative.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"x" * size)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def test_dry_run_uploads_nothing(self):
        out = io.StringIO()
        with patch("cloudinary.uploader.upload") as upload:
            call_command("upload_media_to_cloudinary", stdout=out)
        upload.assert_not_called()
        self.assertIn("SIMULATION : 4 fichier(s)", out.getvalue())
        self.assertIn("[IGNORÉ] format non pris en charge : docs/notes.txt", out.getvalue())
        self.assertNotIn("secret", out.getvalue())

    def test_upload_uses_same_names_and_resource_types(self):
        out = io.StringIO()
        with patch("cloudinary.uploader.upload", return_value={"public_id": "x"}) as upload:
            call_command("upload_media_to_cloudinary", "--yes", stdout=out)
        calls = {c.kwargs["public_id"]: c.kwargs for c in upload.call_args_list}
        self.assertEqual(calls["media/settings/logo"]["resource_type"], "image")
        self.assertEqual(calls["media/properties/generated_tours/v"]["resource_type"], "video")
        self.assertIn("media/id_documents/cni", calls)
        self.assertFalse(calls["media/settings/logo"]["overwrite"])
        self.assertIn("4 envoyé(s)", out.getvalue())

    def test_exclude_and_existing(self):
        out = io.StringIO()
        with patch("cloudinary.uploader.upload", return_value={"existing": True}) as upload:
            call_command("upload_media_to_cloudinary", "--yes", "--exclude", "id_documents", stdout=out)
        self.assertNotIn("media/id_documents/cni", {c.kwargs["public_id"] for c in upload.call_args_list})
        self.assertIn("3 déjà présent(s)", out.getvalue())

    def test_failures_are_reported(self):
        with patch("cloudinary.uploader.upload", side_effect=RuntimeError("quota")):
            with self.assertRaises(CommandError):
                call_command("upload_media_to_cloudinary", "--yes", stdout=io.StringIO())

    @override_settings(CLOUDINARY_URL="")
    def test_requires_cloudinary_url(self):
        with self.assertRaises(CommandError):
            call_command("upload_media_to_cloudinary", stdout=io.StringIO())


class MediaUrlTests(TestCase):
    def test_logo_url_uses_storage_url_when_remote(self):
        from site_settings.models import SiteSettings

        settings_obj = SiteSettings.load()
        settings_obj.logo.name = "settings/logo.png"
        with patch("django.core.files.storage.default_storage.url", return_value="https://res.cloudinary.com/demo/image/upload/v1/media/settings/logo.png"):
            self.assertTrue(settings_obj.logo_url.startswith("https://res.cloudinary.com/"))
        self.assertEqual(settings_obj.logo_url, "/media/settings/logo.png")  # stockage local inchangé

    def test_admin_default_avatar_goes_through_storage(self):
        from accounts.models import User

        admin = User(username="adm", role=User.Role.ADMIN)
        with patch("django.core.files.storage.default_storage.url", return_value="https://res.cloudinary.com/demo/x.png") as url:
            self.assertEqual(admin.get_avatar_url(), "https://res.cloudinary.com/demo/x.png")
        url.assert_called_once_with("settings/ChatGPT_Image_26_août_2026_14_32_40.png")
