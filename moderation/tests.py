from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from payments.tests import make_property
from properties.models import Property

from .models import ListingReport

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


@override_settings(STORAGES=SIMPLE_STATIC)
class ReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="x-Pass-123", role=User.Role.ADMIN)
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.reporter = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.url = reverse("properties:report", args=[self.prop.slug])

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_report_created_and_admin_notified(self):
        self.client.force_login(self.reporter)
        self.client.post(self.url, {"reason": "off_platform", "details": "On me demande un acompte par Mobile Money"})
        report = ListingReport.objects.get()
        self.assertEqual(report.status, "open")
        self.assertTrue(Notification.objects.filter(user=self.admin, title="Annonce signalée").exists())
        self.assertFalse(Notification.objects.filter(user=self.owner, title="Annonce signalée").exists())

    def test_no_duplicate_open_report_and_owner_cannot_report(self):
        self.client.force_login(self.reporter)
        self.client.post(self.url, {"reason": "scam"})
        self.client.post(self.url, {"reason": "scam"})
        self.assertEqual(ListingReport.objects.count(), 1)
        self.client.force_login(self.owner)
        self.client.post(self.url, {"reason": "scam"})
        self.assertEqual(ListingReport.objects.count(), 1)

    def test_invalid_reason_rejected(self):
        self.client.force_login(self.reporter)
        self.client.post(self.url, {"reason": "nimporte"})
        self.assertFalse(ListingReport.objects.exists())

    def test_only_admin_moderates_and_can_unpublish(self):
        report = ListingReport.objects.create(property=self.prop, reporter=self.reporter, reason="fake")
        detail = reverse("dashboard:admin_listing_report", args=[report.pk])
        for user in (self.reporter, self.owner):
            self.client.force_login(user)
            self.client.post(detail, {"action": "action_taken", "unpublish": "on"})
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_published)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("dashboard:admin_listing_reports")), self.prop.title)
        self.client.post(detail, {"action": "action_taken", "unpublish": "on", "admin_note": "Fraude confirmée"})
        report.refresh_from_db()
        self.prop.refresh_from_db()
        self.assertEqual(report.status, "action_taken")
        self.assertFalse(self.prop.is_published)
        self.assertEqual(report.handled_by, self.admin)

    def test_detail_page_shows_report_link(self):
        self.client.force_login(self.reporter)
        self.assertContains(self.client.get(self.prop.get_absolute_url()), "Signaler cette annonce")
