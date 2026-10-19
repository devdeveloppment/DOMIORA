from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from messaging.models import Conversation
from properties.models import Property, PropertyUnlock

from .models import PaymentAttempt, PaymentEvent
from .relations import has_owner_relation
from .services import verify_attempt


from django.conf import settings as dj_settings

SIMPLE_STATIC = {**dj_settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def make_property(owner, title="Villa à Agoè", **kw):
    data = dict(
        owner=owner, title=title, property_type=Property.PropertyType.VILLA,
        transaction_type=Property.TransactionType.LOCATION, price=250_000, currency="XOF",
        country="TG", city="Lomé", bedrooms=3, bathrooms=2, surface_area=180,
        is_published=True, is_validated=True,
    )
    data.update(kw)
    return Property.objects.create(**data)


@override_settings(PAYMENT_MODE="simulation", CONTACT_FEE_AMOUNT=500, STORAGES=SIMPLE_STATIC)
class SimulationPaymentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.APPROVED)
        self.client_user = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.prop2 = make_property(self.owner, title="Appartement à Bè")
        self.client.force_login(self.client_user)

    def start(self, prop=None):
        resp = self.client.post(reverse("properties:payment_redirect", args=[(prop or self.prop).slug]))
        attempt = PaymentAttempt.objects.latest("created_at")
        self.assertRedirects(resp, reverse("payments:simulator", args=[attempt.reference]), fetch_redirect_response=False)
        return attempt

    def decide(self, attempt, outcome):
        return self.client.post(reverse("payments:simulator_decide", args=[attempt.reference]), {"outcome": outcome})

    def test_amount_comes_from_configuration(self):
        with self.settings(CONTACT_FEE_AMOUNT=750):
            attempt = self.start()
        self.assertEqual(attempt.amount, 750)
        self.assertEqual(attempt.provider, "simulation")

    def test_simulator_page_shows_demo_banner(self):
        attempt = self.start()
        resp = self.client.get(reverse("payments:simulator", args=[attempt.reference]))
        self.assertContains(resp, "MODE DÉMONSTRATION — AUCUN ARGENT RÉEL")

    def test_success_creates_single_owner_relation(self):
        attempt = self.start()
        resp = self.decide(attempt, "approved")
        self.assertRedirects(resp, reverse("payments:return", args=[attempt.reference]), fetch_redirect_response=False)
        self.client.get(resp.url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, PaymentAttempt.Status.APPROVED)
        self.assertTrue(attempt.relation_granted)
        self.assertEqual(PropertyUnlock.objects.filter(user=self.client_user).count(), 1)
        self.assertEqual(Conversation.objects.filter(buyer=self.client_user, owner=self.owner).count(), 1)
        self.assertTrue(has_owner_relation(self.client_user, self.owner))

    def test_no_second_payment_for_same_owner(self):
        attempt = self.start()
        self.decide(attempt, "approved")
        resp = self.client.post(reverse("properties:payment_redirect", args=[self.prop2.slug]))
        self.assertRedirects(resp, reverse("properties:detail", args=[self.prop2.slug]), fetch_redirect_response=False)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_declined_and_canceled_create_nothing(self):
        for outcome, status in (("declined", "declined"), ("canceled", "canceled")):
            attempt = self.start()
            self.decide(attempt, outcome)
            attempt.refresh_from_db()
            self.assertEqual(attempt.status, status)
        self.assertFalse(PropertyUnlock.objects.exists())

    def test_pending_then_resume_after_approval(self):
        attempt = self.start()
        self.decide(attempt, "pending")
        resp = self.client.get(reverse("payments:return", args=[attempt.reference]))
        self.assertContains(resp, "Paiement en attente")
        self.assertFalse(PropertyUnlock.objects.exists())
        # Le fournisseur finit par approuver ; le client relance la vérification.
        PaymentAttempt.objects.filter(pk=attempt.pk).update(simulated_outcome="approved")
        resp = self.client.post(reverse("payments:recheck", args=[attempt.reference]), follow=True)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "approved")
        self.assertEqual(PropertyUnlock.objects.count(), 1)

    def test_pending_attempt_is_reused_not_duplicated(self):
        first = self.start()
        second = self.start()
        self.assertEqual(first.pk, second.pk)

    def test_timeout_and_technical_error_keep_pending(self):
        for outcome in ("timeout", "error"):
            attempt = self.start()
            self.decide(attempt, outcome)
            resp = self.client.get(reverse("payments:return", args=[attempt.reference]))
            attempt.refresh_from_db()
            self.assertEqual(attempt.status, "pending")
            self.assertTrue(attempt.last_error)
            self.assertContains(resp, "Vérification impossible")
            PaymentAttempt.objects.filter(pk=attempt.pk).update(status="canceled")
        self.assertFalse(PropertyUnlock.objects.exists())

    def test_expired_pending_attempt(self):
        attempt = self.start()
        PaymentAttempt.objects.filter(pk=attempt.pk).update(
            simulated_outcome="pending", created_at=timezone.now() - timedelta(hours=2))
        attempt.refresh_from_db()
        attempt = verify_attempt(attempt)
        self.assertEqual(attempt.status, "expired")

    def test_duplicate_notification_is_idempotent(self):
        attempt = self.start()
        self.decide(attempt, "approved_duplicate")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "approved")
        self.assertEqual(PropertyUnlock.objects.count(), 1)
        notify_events = PaymentEvent.objects.filter(attempt=attempt, source="simulator")
        self.assertEqual(notify_events.count(), 1)

    def test_incomplete_return_relation_via_notification(self):
        attempt = self.start()
        resp = self.decide(attempt, "abandon")
        self.assertRedirects(resp, reverse("dashboard:client_unlocked"), fetch_redirect_response=False)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "approved")
        self.assertTrue(has_owner_relation(self.client_user, self.owner))

    def test_browser_cannot_forge_status(self):
        attempt = self.start()
        self.decide(attempt, "pending")
        # Paramètres falsifiés sur l'ancienne et la nouvelle URL de retour.
        self.client.get(reverse("properties:payment_confirmation", args=[self.prop.slug]) + "?status=approved&id=123")
        self.client.get(reverse("payments:return", args=[attempt.reference]) + "?status=approved")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")
        self.assertFalse(PropertyUnlock.objects.exists())
        # Scénario inconnu refusé.
        self.decide(attempt, "hacked")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")

    def test_terminal_status_never_changes(self):
        attempt = self.start()
        self.decide(attempt, "declined")
        self.decide(attempt, "approved")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "declined")
        self.assertFalse(PropertyUnlock.objects.exists())

    def test_other_user_cannot_drive_attempt(self):
        attempt = self.start()
        intruder = User.objects.create_user("intrus", password="x-Pass-123", role=User.Role.CLIENT)
        self.client.force_login(intruder)
        self.assertEqual(self.decide(attempt, "approved").status_code, 404)
        self.assertEqual(self.client.get(reverse("payments:return", args=[attempt.reference])).status_code, 404)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")

    def test_owner_role_cannot_pay(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_guest_creates_account_before_payment(self):
        self.client.logout()
        resp = self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]), {
            "first_name": "Kossi", "last_name": "Mensah", "phone": "90000000", "email": "kossi@example.tg",
            "username": "kossi", "password1": "Lome-Tg-2026!", "password2": "Lome-Tg-2026!",
        })
        user = User.objects.get(username="kossi")
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertTrue(user.check_password("Lome-Tg-2026!"))
        attempt = PaymentAttempt.objects.get(client=user)
        self.assertRedirects(resp, reverse("payments:simulator", args=[attempt.reference]), fetch_redirect_response=False)
        self.assertNotIn("pending_payment", self.client.session)
        self.assertFalse(PropertyUnlock.objects.exists())

    def test_guest_cannot_take_over_existing_email(self):
        self.client_user.email = "deja@example.tg"
        self.client_user.save()
        self.client.logout()
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]), {
            "first_name": "A", "last_name": "B", "phone": "1", "email": "deja@example.tg",
            "username": "autre", "password1": "Lome-Tg-2026!", "password2": "Lome-Tg-2026!",
        })
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password("x-Pass-123"))
        self.assertFalse(User.objects.filter(username="autre").exists())

    def test_legacy_free_unlock_routes_no_longer_grant_access(self):
        self.client.get(reverse("accounts:register_client_post_payment", args=[self.prop.slug]))
        self.assertFalse(PropertyUnlock.objects.exists())


@override_settings(PAYMENT_MODE="fedapay", FEDAPAY_SECRET_KEY="sk_test_dummy", STORAGES=SIMPLE_STATIC)
class SimulationIsolationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.client_user = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.client.force_login(self.client_user)

    def test_simulator_unavailable_outside_simulation_mode(self):
        attempt = PaymentAttempt.objects.create(client=self.client_user, owner=self.owner, property=self.prop,
                                                provider="simulation", amount=500, simulated_outcome="approved")
        self.assertEqual(self.client.get(reverse("payments:simulator", args=[attempt.reference])).status_code, 404)
        self.assertEqual(self.client.post(reverse("payments:simulator_decide", args=[attempt.reference]),
                                          {"outcome": "approved"}).status_code, 404)
        # Même avec un « résultat » simulé enregistré, la tentative n'est jamais confirmée.
        self.client.get(reverse("payments:return", args=[attempt.reference]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")
        self.assertFalse(PropertyUnlock.objects.exists())

    @mock.patch("payments.providers.requests.get")
    def test_fedapay_return_verifies_server_side(self, mock_get):
        attempt = PaymentAttempt.objects.create(client=self.client_user, owner=self.owner, property=self.prop,
                                                provider="fedapay", amount=500, provider_transaction_id="42")
        mock_get.return_value.json.return_value = {"v1/transaction": {"id": 42, "status": "declined"}}
        mock_get.return_value.raise_for_status.return_value = None
        self.client.get(reverse("payments:return", args=[attempt.reference]) + "?status=approved")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "declined")
        self.assertTrue(mock_get.called)

    def test_webhook_rejects_bad_signature(self):
        resp = self.client.post(reverse("payments:fedapay_webhook"), data="{}", content_type="application/json",
                                HTTP_X_FEDAPAY_SIGNATURE="bad")
        self.assertEqual(resp.status_code, 403)


class SettingsSafetyTests(TestCase):
    def test_production_never_defaults_to_simulation(self):
        import importlib
        import os
        env = {"DEBUG": "False", "PAYMENT_MODE": "simulation"}
        with mock.patch.dict(os.environ, env):
            import config.settings as s
            s = importlib.reload(s)
            self.assertEqual(s.PAYMENT_MODE, "fedapay")
        importlib.reload(s)
