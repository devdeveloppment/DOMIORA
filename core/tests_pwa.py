import json

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


@override_settings(STORAGES=SIMPLE_STATIC)
class PwaTests(TestCase):
    def test_manifest(self):
        resp = self.client.get(reverse("core:pwa_manifest"))
        self.assertEqual(resp["Content-Type"], "application/manifest+json")
        data = json.loads(resp.content)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(len(data["icons"]), 2)

    def test_service_worker_scope_and_privacy(self):
        resp = self.client.get(reverse("core:service_worker"))
        self.assertEqual(resp["Service-Worker-Allowed"], "/")
        body = resp.content.decode()
        # Seul /static/ est mis en cache ; les navigations ne sont jamais stockées.
        self.assertIn('url.pathname.startsWith("/static/")', body)
        self.assertNotIn("c.put(req, copy));\n      }\n    }));\n    return;\n  }\n  if (req.mode", body)

    def test_offline_page(self):
        self.assertContains(self.client.get(reverse("core:offline")), "hors connexion")

    def test_base_registers_service_worker(self):
        resp = self.client.get(reverse("core:about"))
        self.assertContains(resp, 'rel="manifest"')
        self.assertContains(resp, "serviceWorker")


@override_settings(STORAGES=SIMPLE_STATIC)
class HomeGlideTests(TestCase):
    def test_glide_runs_once_and_respects_reduced_motion(self):
        from accounts.models import User
        from payments.tests import make_property

        owner = User.objects.create_user("p", password="x-Pass-123", role=User.Role.OWNER)
        make_property(owner)
        body = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("domiora-glide 1.6s", body)
        self.assertIn(" 1 both", body)          # une seule itération
        self.assertNotIn("infinite", body.split("domiora-glide")[1][:200])
        self.assertIn("prefers-reduced-motion: reduce", body)
