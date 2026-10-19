"""Tests de l'audit complémentaire : isolation de la simulation, relations, rôle VERIFIER."""
import io
import json
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from agents.models import Agent
from properties.models import PropertyUnlock
from rental_requests.models import PropertyRequest

from .models import PaymentAttempt
from .services import verify_attempt
from .tests import SIMPLE_STATIC, make_property

NO_NETWORK = mock.patch("payments.providers.requests", **{
    "post.side_effect": AssertionError("appel FedaPay interdit"),
    "get.side_effect": AssertionError("appel FedaPay interdit"),
})


def users():
    owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
    client = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
    return owner, client


@override_settings(PAYMENT_MODE="simulation", PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY=False, STORAGES=SIMPLE_STATIC,
                   FEDAPAY_SECRET_KEY="sk_live_should_never_be_used")
class SimulationNeverCallsFedaPay(TestCase):
    def setUp(self):
        self.owner, self.client_user = users()
        self.prop = make_property(self.owner)
        self.client.force_login(self.client_user)

    def test_full_simulated_flow_without_network(self):
        with NO_NETWORK, mock.patch("properties.fedapay.requests") as legacy:
            legacy.post.side_effect = legacy.get.side_effect = AssertionError("appel FedaPay interdit")
            self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
            attempt = PaymentAttempt.objects.get()
            for outcome in ("pending", "timeout", "error"):
                PaymentAttempt.objects.filter(pk=attempt.pk).update(simulated_outcome=outcome)
                self.client.get(reverse("payments:return", args=[attempt.reference]))
            self.client.post(reverse("payments:simulator_decide", args=[attempt.reference]), {"outcome": "approved_duplicate"})
            self.client.post(reverse("core:donate"), {"amount": "1000"})
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "approved")
        self.assertEqual(PropertyUnlock.objects.count(), 1)

    def test_fedapay_attempt_not_verified_in_simulation_mode(self):
        attempt = PaymentAttempt.objects.create(client=self.client_user, owner=self.owner, property=self.prop,
                                                provider="fedapay", amount=500, provider_transaction_id="7")
        with NO_NETWORK:
            verify_attempt(attempt)
            self.client.get(reverse("payments:return", args=[attempt.reference]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")

    def test_fedapay_webhook_ignored_in_simulation_mode(self):
        with NO_NETWORK:
            resp = self.client.post(reverse("payments:fedapay_webhook"), data=json.dumps({"entity": {"id": 1}}),
                                    content_type="application/json")
        self.assertEqual(resp.content, b"ignored")


@override_settings(PAYMENT_MODE="simulation", PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY=True, STORAGES=SIMPLE_STATIC)
class DemoIsolationTests(TestCase):
    def setUp(self):
        self.owner, self.client_user = users()
        self.prop = make_property(self.owner)

    def test_real_accounts_cannot_use_simulation(self):
        self.client.force_login(self.client_user)
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        self.assertFalse(PaymentAttempt.objects.exists())
        self.assertFalse(PropertyUnlock.objects.exists())

    def test_demo_client_with_real_owner_refused(self):
        self.client_user.is_demo = True
        self.client_user.save()
        self.client.force_login(self.client_user)
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_guest_signup_refused_in_isolated_demo(self):
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]), {
            "first_name": "A", "last_name": "B", "phone": "1", "username": "invite",
            "password1": "Lome-Tg-2026!", "password2": "Lome-Tg-2026!"})
        self.assertFalse(User.objects.filter(username="invite").exists())

    def test_demo_pair_works(self):
        User.objects.filter(pk__in=[self.owner.pk, self.client_user.pk]).update(is_demo=True)
        self.client.force_login(User.objects.get(pk=self.client_user.pk))
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        attempt = PaymentAttempt.objects.get()
        self.client.post(reverse("payments:simulator_decide", args=[attempt.reference]), {"outcome": "approved"})
        self.assertEqual(PropertyUnlock.objects.count(), 1)

    def test_defense_in_depth_if_demo_flag_removed(self):
        attempt = PaymentAttempt.objects.create(client=self.client_user, owner=self.owner, property=self.prop,
                                                provider="simulation", amount=500, simulated_outcome="approved")
        verify_attempt(attempt)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "failed")
        self.assertFalse(PropertyUnlock.objects.exists())

    def test_demo_banner_visible(self):
        self.assertContains(self.client.get(reverse("core:about")), "MODE DÉMONSTRATION — AUCUN ARGENT RÉEL")


@override_settings(STORAGES=SIMPLE_STATIC)
class VisitRequiresRelationTests(TestCase):
    def setUp(self):
        self.owner, self.client_user = users()
        self.prop = make_property(self.owner)
        self.agent = Agent.objects.create(user=self.owner)
        self.client.force_login(self.client_user)

    def test_web_request_without_relation_refused(self):
        resp = self.client.post(reverse("rental_requests:create"), {"property_id": self.prop.pk, "request_type": "visite"})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(PropertyRequest.objects.exists())

    def test_web_request_with_relation_accepted(self):
        PropertyUnlock.objects.create(user=self.client_user, property=self.prop)
        self.client.post(reverse("rental_requests:create"), {"property_id": self.prop.pk, "request_type": "visite"})
        self.assertTrue(PropertyRequest.objects.filter(user=self.client_user).exists())

    def test_api_request_without_relation_refused(self):
        resp = self.client.post(reverse("propertyrequest-list"), {"property": self.prop.pk, "request_type": "visite"})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(PropertyRequest.objects.exists())

    def test_appointment_without_relation_refused(self):
        from appointments.models import Appointment
        self.client.post(reverse("appointments:book", args=[self.agent.pk]),
                         {"scheduled_at": "2026-12-01T10:00", "property_id": self.prop.pk})
        self.client.logout()
        self.client.post(reverse("appointments:book", args=[self.agent.pk]),
                         {"guest_name": "X Y", "guest_email": "x@y.tg", "guest_phone": "1", "scheduled_at": "2026-12-01T10:00"})
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(User.objects.filter(email="x@y.tg").exists())

    def test_public_api_hides_address(self):
        self.prop.address = "Rue 45 Tokoin"
        self.prop.save()
        body = self.client.get(reverse("property-detail", args=[self.prop.slug])).content.decode()
        self.assertNotIn("Rue 45 Tokoin", body)
        self.assertEqual(json.loads(self.client.get(reverse("property-list") + "?search=Tokoin").content)["count"], 0)


@override_settings(STORAGES=SIMPLE_STATIC, PAYMENT_MODE="simulation", PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY=False)
class VerifierRestrictionsTests(TestCase):
    def setUp(self):
        self.owner, _ = users()
        self.prop = make_property(self.owner)
        self.verifier = User.objects.create_user("verif", password="x-Pass-123", role=User.Role.VERIFIER)
        self.client.force_login(self.verifier)

    def test_verifier_has_no_client_owner_or_admin_rights(self):
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        self.assertFalse(PaymentAttempt.objects.exists())
        self.client.post(reverse("messaging:start_conversation", args=[self.owner.pk]), {"property_id": self.prop.pk})
        from messaging.models import Conversation
        self.assertFalse(Conversation.objects.exists())
        self.client.post(reverse("ratings:create", args=[self.owner.pk]), {"rating": 1, "comment": "x"})
        from ratings.models import Review
        self.assertFalse(Review.objects.exists())
        for name, args in (("dashboard:owner_property_create", []), ("dashboard:admin_users", []),
                           ("dashboard:admin_listing_reports", []), ("dashboard:client_unlocked", [])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302, name)
        self.assertFalse(self.verifier.is_staff)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_verifier_does_not_see_private_address(self):
        self.prop.address = "Rue 99 Bè"
        self.prop.save()
        self.assertNotContains(self.client.get(self.prop.get_absolute_url()), "Rue 99 Bè")

    def test_weak_verifier_password_refused(self):
        admin = User.objects.create_user("adm", password="x-Pass-123", role=User.Role.ADMIN)
        self.client.force_login(admin)
        self.client.post(reverse("dashboard:admin_verifier_create"), {"username": "v2", "password": "1234567890"})
        self.assertFalse(User.objects.filter(username="v2").exists())


class AuditCommandTests(TestCase):
    def test_never_grants_unproven_and_needs_confirm(self):
        owner = User.objects.create_user("p", password="x-Pass-123", role=User.Role.OWNER,
                                         verification_status=User.VerificationStatus.APPROVED)
        out = io.StringIO()
        call_command("audit_verification", stdout=out)
        self.assertIn(f"id={owner.pk}", out.getvalue())
        call_command("audit_verification", "--fix", stdout=out)
        call_command("audit_verification", "--fix", "--confirm", stdout=out)
        owner.refresh_from_db()
        self.assertFalse(owner.can_publish_properties)
        self.assertEqual(owner.verification_status, User.VerificationStatus.APPROVED)
