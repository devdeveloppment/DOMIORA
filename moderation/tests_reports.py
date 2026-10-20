"""Circuit complet des signalements : soumission, pièces jointes, traitement, suivi, permissions."""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from payments.tests import SIMPLE_STATIC, make_property
from properties.models import Property, PropertyView

from .models import ListingReport, ReportEvent
from .services import ReportError, process_report, submit_report

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64
TMP_PRIVATE = tempfile.mkdtemp(prefix="domiora-reports-")


@override_settings(STORAGES=SIMPLE_STATIC, PRIVATE_MEDIA_BACKEND="filesystem", PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class ReportFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="x-Pass-123", role=User.Role.ADMIN)
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.stranger_owner = User.objects.create_user("inconnu", password="x-Pass-123", role=User.Role.OWNER)
        self.reporter = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.other_client = User.objects.create_user("client2", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.stranger_prop = make_property(self.stranger_owner, title="Bien jamais consulté")
        PropertyView.objects.create(property=self.prop, user=self.reporter)

    # --- Soumission ---------------------------------------------------------------

    def test_client_form_creates_report_linked_to_property_and_owner(self):
        self.client.force_login(self.reporter)
        resp = self.client.post(reverse("dashboard:client_report_new"), {
            "category": "listing", "property": self.prop.pk, "reason": "fake", "details": "Photos copiées d'un autre site",
        })
        report = ListingReport.objects.get()
        self.assertRedirects(resp, reverse("dashboard:client_report_detail", args=[report.pk]))
        self.assertEqual(report.reported_owner, self.owner)
        self.assertEqual(report.status, "open")
        self.assertTrue(ReportEvent.objects.filter(report=report, action="created", is_public=True).exists())
        self.assertTrue(Notification.objects.filter(user=self.admin, link__endswith=f"/{report.pk}/").exists())
        self.assertFalse(Notification.objects.filter(user=self.owner).exists())  # le propriétaire n'est jamais prévenu

    def test_owner_and_scam_categories(self):
        submit_report(self.reporter, category="owner", reason="behavior", reported_owner=self.owner, details="Menaces")
        with self.assertRaises(ReportError):
            submit_report(self.reporter, category="scam_attempt", reason="off_platform", details="trop court")
        scam = submit_report(self.reporter, category="scam_attempt", reason="off_platform",
                             details="On m'a demandé 50 000 FCFA par Mobile Money avant la visite.")
        self.assertIsNone(scam.property)
        self.assertEqual(ListingReport.objects.count(), 2)

    def test_form_refuses_targets_the_client_never_interacted_with(self):
        self.client.force_login(self.reporter)
        self.client.post(reverse("dashboard:client_report_new"), {
            "category": "listing", "property": self.stranger_prop.pk, "reason": "fake"})
        self.client.post(reverse("dashboard:client_report_new"), {
            "category": "owner", "owner": self.stranger_owner.pk, "reason": "behavior"})
        self.assertFalse(ListingReport.objects.exists())
        page = self.client.get(reverse("dashboard:client_report_new")).content.decode()
        self.assertIn(self.prop.title, page)
        self.assertNotIn(self.stranger_prop.title, page)
        self.assertNotIn("inconnu", page)

    def test_duplicates_and_daily_limit(self):
        submit_report(self.reporter, reason="fake", property_obj=self.prop)
        with self.assertRaises(ReportError):
            submit_report(self.reporter, reason="scam", property_obj=self.prop)
        for i in range(4):
            submit_report(self.reporter, category="scam_attempt", reason="scam", details=f"Tentative numéro {i} décrite ici")
        with self.assertRaises(ReportError):
            submit_report(self.reporter, category="scam_attempt", reason="scam", details="Une sixième tentative aujourd'hui")

    def test_cannot_report_yourself(self):
        with self.assertRaises(ReportError):
            submit_report(self.owner, category="owner", reason="other", reported_owner=self.owner)

    # --- Pièces jointes -----------------------------------------------------------

    def test_valid_attachments_stored_privately(self):
        for name, data in (("capture.png", PNG), ("echange.pdf", PDF)):
            report = submit_report(self.reporter, category="scam_attempt", reason="scam",
                                   details=f"Preuve jointe dans le fichier {name}",
                                   attachment=SimpleUploadedFile(name, data))
            self.assertTrue(report.attachment.name.startswith("reports/"))
            with self.assertRaises(NotImplementedError):
                report.attachment.url  # jamais d'URL publique

    def test_invalid_attachments_rejected(self):
        cases = [
            SimpleUploadedFile("script.exe", b"MZ" + b"\x00" * 30),
            SimpleUploadedFile("faux.png", b"<?php echo 1; ?>" + b"\x00" * 30, content_type="image/png"),
            SimpleUploadedFile("enorme.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024 + 1)),
        ]
        for upload in cases:
            with self.assertRaises(ReportError, msg=upload.name):
                submit_report(self.reporter, category="scam_attempt", reason="scam",
                              details="Description suffisamment longue", attachment=upload)
        self.assertFalse(ListingReport.objects.exists())

    def test_attachment_visible_only_to_admin_and_author(self):
        report = submit_report(self.reporter, category="scam_attempt", reason="scam", details="Capture de la conversation",
                               attachment=SimpleUploadedFile("capture.png", PNG))
        url = reverse("dashboard:report_attachment", args=[report.pk])
        for user, expected in ((self.other_client, 404), (self.owner, 404), (self.reporter, 200), (self.admin, 200)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, expected, user.username)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)

    # --- Traitement administratif ---------------------------------------------------

    def test_admin_processing_is_audited_and_notifies_reporter(self):
        report = submit_report(self.reporter, reason="fake", property_obj=self.prop)
        self.client.force_login(self.admin)
        detail = reverse("dashboard:admin_listing_report", args=[report.pk])
        self.client.post(detail, {"action": "reviewing", "admin_note": "Vérifier les photos"})
        self.client.post(detail, {"action": "", "admin_note": "Photos trouvées sur un autre site"})
        self.client.post(detail, {"action": "action_taken", "public_message": "Annonce retirée, merci.", "unpublish": "on"})
        report.refresh_from_db()
        self.prop.refresh_from_db()
        self.assertEqual(report.status, "action_taken")
        self.assertFalse(self.prop.is_published)
        self.assertTrue(report.listing_unpublished)
        actions = list(report.events.values_list("action", flat=True))
        self.assertEqual(actions, ["created", "note", "status", "note", "status", "message", "unpublished"])
        self.assertEqual(report.events.filter(action="note").count(), 2)  # les notes ne s'écrasent plus
        self.assertTrue(Notification.objects.filter(user=self.reporter, message__contains="Annonce retirée").exists())

    def test_no_automatic_sanction(self):
        """Ni la création, ni un classement sans suite, ni une mise en examen ne touchent l'annonce ou le propriétaire."""
        report = submit_report(self.reporter, reason="scam", property_obj=self.prop)
        process_report(report, self.admin, status="reviewing")
        process_report(report, self.admin, status="dismissed")
        self.prop.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertTrue(self.prop.is_published)
        self.assertTrue(self.owner.is_active)
        with self.assertRaises(ReportError):
            process_report(report, self.admin, status="reviewing", unpublish=True)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_published)

    def test_admin_list_filters_by_type(self):
        submit_report(self.reporter, reason="fake", property_obj=self.prop)
        submit_report(self.reporter, category="scam_attempt", reason="scam", details="Demande d'argent par WhatsApp")
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:admin_listing_reports"), {"type": "scam_attempt"})
        self.assertEqual(len(resp.context["page_obj"]), 1)
        self.assertEqual(resp.context["counts"]["open"], 2)

    # --- Suivi client et confidentialité ----------------------------------------------

    def test_client_sees_public_history_but_never_internal_notes(self):
        report = submit_report(self.reporter, reason="fake", property_obj=self.prop)
        process_report(report, self.admin, status="reviewing", internal_note="NOTE-INTERNE-SECRETE")
        self.client.force_login(self.reporter)
        resp = self.client.get(reverse("dashboard:client_report_detail", args=[report.pk]))
        self.assertContains(resp, "En cours d&#x27;examen")
        self.assertNotContains(resp, "NOTE-INTERNE-SECRETE")
        self.assertEqual([e.action for e in resp.context["events"]], ["created", "status"])
        listing = self.client.get(reverse("dashboard:client_reports"))
        self.assertEqual(list(listing.context["reports"]), [report])

    def test_unauthorized_access(self):
        report = submit_report(self.reporter, reason="fake", property_obj=self.prop)
        self.client.force_login(self.other_client)
        self.assertEqual(self.client.get(reverse("dashboard:client_report_detail", args=[report.pk])).status_code, 404)
        self.assertEqual(list(self.client.get(reverse("dashboard:client_reports")).context["reports"]), [])
        for user in (self.reporter, self.owner):
            self.client.force_login(user)
            resp = self.client.post(reverse("dashboard:admin_listing_report", args=[report.pk]), {"action": "dismissed"})
            self.assertNotEqual(resp.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, "open")
        self.client.force_login(self.owner)
        self.assertNotEqual(self.client.get(reverse("dashboard:client_reports")).status_code, 200)

    def test_report_survives_listing_deletion(self):
        report = submit_report(self.reporter, reason="fake", property_obj=self.prop)
        Property.objects.filter(pk=self.prop.pk).delete()
        report.refresh_from_db()
        self.assertIsNone(report.property)
        self.assertEqual(report.reported_owner, self.owner)
        self.assertEqual(report.events.count(), 1)

    # --- Statistiques --------------------------------------------------------------

    def test_dashboard_counts_are_synchronised(self):
        report = submit_report(self.reporter, reason="fake", property_obj=self.prop)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:admin_overview")).context["counts"]["reports_active"], 1)
        process_report(report, self.admin, status="dismissed")
        self.assertEqual(self.client.get(reverse("dashboard:admin_overview")).context["counts"]["reports_active"], 0)
