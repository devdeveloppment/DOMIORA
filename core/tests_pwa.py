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
    def test_marquee_loops_accessibly_and_respects_reduced_motion(self):
        """Défilé continu : une copie visible, une copie décorative (aria-hidden, hors tabulation)."""
        from django.conf import settings

        from accounts.models import User
        from payments.tests import make_property

        owner = User.objects.create_user("p", password="x-Pass-123", role=User.Role.OWNER)
        prop = make_property(owner)
        body = self.client.get(reverse("core:home")).content.decode()
        self.assertEqual(body.count('class="domiora-marquee__group"'), 2)
        self.assertEqual(body.count('class="domiora-marquee__group" role="list" aria-hidden="true"'), 1)
        marquee = body.split('class="domiora-marquee__track"')[1].split("</section>")[0]
        self.assertEqual(marquee.count(f'alt="{prop.title}"'), 1)  # la copie n'est pas annoncée deux fois
        self.assertIn('tabindex="-1"', body)
        with open(settings.BASE_DIR / "static/css/design-system.css", encoding="utf-8") as handle:
            css = handle.read()
        self.assertIn("domiora-marquee calc(var(--marquee-items, 6) * 5s) linear infinite", css)
        self.assertIn("animation-play-state: paused", css)
        reduced = "".join(css.split("@media (prefers-reduced-motion: reduce)")[1:])
        self.assertIn(".domiora-marquee__group { animation: none;", reduced)
        self.assertIn(".domiora-skyline__layer { animation: none; }", reduced)


@override_settings(STORAGES=SIMPLE_STATIC)
class StartupRegressionTests(TestCase):
    def test_favicon_redirects_to_site_icon(self):
        resp = self.client.get("/favicon.ico")
        self.assertEqual(resp.status_code, 301)
        self.assertIn("pwa/icon-192", resp["Location"])

    def test_urls_load_without_heavy_ai_sdk(self):
        """Le SDK Anthropic n'est importé qu'au premier appel : sinon la 1re requête dépassait le délai gunicorn."""
        import subprocess
        import sys

        code = ("import os,sys,django;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';django.setup();"
                "from django.urls import get_resolver;get_resolver().url_patterns;print('anthropic' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "False", out.stderr[-500:])

    def test_gunicorn_timeout_raised(self):
        from django.conf import settings

        with open(settings.BASE_DIR / "start.sh", encoding="utf-8") as handle:
            self.assertIn("--timeout 120", handle.read())
