from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import IdentityVerificationRequest, User
from notifications.models import Notification
from payments.tests import make_property
from properties.models import PropertyUnlock

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


@override_settings(STORAGES=SIMPLE_STATIC)
class ApiPrivacyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "proprio", email="secret@example.tg", phone="+22890000000", whatsapp_number="+22891111111",
            password="x-Pass-123", role=User.Role.OWNER,
        )
        self.prop = make_property(self.owner)
        self.client_user = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)

    def test_public_property_api_hides_owner_contacts(self):
        for url in (reverse("property-list"), reverse("property-detail", args=[self.prop.slug])):
            body = self.client.get(url).content.decode()
            self.assertNotIn("secret@example.tg", body)
            self.assertNotIn("+22890000000", body)
            self.assertNotIn("+22891111111", body)

    def test_property_api_is_read_only(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(reverse("property-detail", args=[self.prop.slug]), {"is_validated": False},
                                 content_type="application/json")
        self.assertEqual(resp.status_code, 405)
        resp = self.client.post(reverse("property-list"), {"title": "x"})
        self.assertEqual(resp.status_code, 405)

    def test_non_admin_cannot_resume_verification(self):
        verification = IdentityVerificationRequest.objects.create(owner=self.owner, id_document_front="a.png",
                                                                  id_document_back="b.png")
        for user in (self.client_user, self.owner):
            self.client.force_login(user)
            resp = self.client.post(reverse("verification_resume", args=[verification.pk]), {"decision": "validated"})
            self.assertEqual(resp.status_code, 403)
        self.owner.refresh_from_db()
        self.assertNotEqual(self.owner.verification_status, User.VerificationStatus.APPROVED)

    def test_non_admin_cannot_push_notifications(self):
        self.client.force_login(self.client_user)
        resp = self.client.post(reverse("admin_notification_webhook"), {
            "notification_type": "info", "title": "x", "message": "y", "user_id": self.owner.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Notification.objects.filter(user=self.owner, title="x").exists())


@override_settings(STORAGES=SIMPLE_STATIC)
class RoleAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.other_owner = User.objects.create_user("autre", password="x-Pass-123", role=User.Role.OWNER)
        self.client_user = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)

    def test_session_dash_role_grants_nothing(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session["dash_role"] = "client"
        session.save()
        resp = self.client.get(reverse("dashboard:client_favorites"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:redirect"))

    def test_payment_does_not_grant_other_role_spaces(self):
        PropertyUnlock.objects.create(user=self.other_owner, property=self.prop)
        self.client.force_login(self.other_owner)
        resp = self.client.get(reverse("dashboard:client_favorites"))
        self.assertEqual(resp.url, reverse("dashboard:redirect"))

    def test_client_cannot_open_admin_panel(self):
        self.client.force_login(self.client_user)
        resp = self.client.get(reverse("dashboard:admin_overview"))
        self.assertEqual(resp.status_code, 302)

    def test_other_owner_does_not_see_private_address(self):
        self.prop.address = "Rue 123 Adresse Privée"
        self.prop.save()
        self.client.force_login(self.other_owner)
        resp = self.client.get(self.prop.get_absolute_url())
        self.assertNotContains(resp, "Rue 123 Adresse Privée")

    def test_guest_property_request_does_not_unlock(self):
        self.client.post(reverse("rental_requests:create"), {
            "property_id": self.prop.pk, "request_type": "visite", "guest_name": "Ama Koffi",
            "guest_email": "ama@example.tg", "guest_phone": "90000000"})
        self.assertFalse(PropertyUnlock.objects.exists())
