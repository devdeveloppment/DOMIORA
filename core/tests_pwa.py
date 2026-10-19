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
