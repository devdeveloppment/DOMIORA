"""Dons : montant libre, statuts, idempotence, séparation test/réel, confirmation serveur."""
import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from payments.tests import SIMPLE_STATIC

from . import donations
from .models import Donation, DonationEvent


@override_settings(PAYMENT_MODE="simulation", STORAGES=SIMPLE_STATIC)
class DonationSimulationTests(TestCase):
    def donate(self, amount):
        cache.clear()  # limite anti-abus (10 tentatives/heure) testée séparément
        return self.client.post(reverse("core:donate"), {"amount": amount, "email": "don@exemple.tg"})

    def decide(self, donation, outcome):
        return self.client.post(reverse("core:donation_simulator", args=[donation.reference]), {"outcome": outcome})

    def test_free_amounts_accepted(self):
        for amount in (300, 500, 700, 1000, 1250, 25000, 1_000_000):
            resp = self.donate(amount)
            donation = Donation.objects.latest("created_at")
            self.assertEqual(donation.amount, amount)
            self.assertRedirects(resp, reverse("core:donation_simulator", args=[donation.reference]))
        self.assertEqual(Donation.objects.count(), 7)

    def test_formatted_amounts_accepted(self):
        self.donate("1 500")
        self.assertEqual(Donation.objects.get().amount, 1500)

    def test_invalid_amounts_rejected_server_side(self):
        for raw in ("", "abc", "-500", "12.5", "0", "50", "99999999999"):
            resp = self.donate(raw)
            self.assertEqual(resp.status_code, 200, raw)
        self.assertFalse(Donation.objects.exists())

    @override_settings(DONATION_MIN_AMOUNT=1)
    def test_minimum_follows_configuration(self):
        self.donate(50)
        self.assertEqual(Donation.objects.get().amount, 50)

    def test_approved_simulation_is_test_and_confirmed_by_server(self):
        self.donate(700)
        donation = Donation.objects.get()
        self.assertTrue(donation.is_test)
        resp = self.decide(donation, "approved")
        self.assertRedirects(resp, reverse("core:donation_return", args=[donation.reference]))
        page = self.client.get(reverse("core:donation_return", args=[donation.reference]))
        donation.refresh_from_db()
        self.assertEqual(donation.status, "approved")
        self.assertContains(page, "Merci pour votre don")
        self.assertContains(page, "Don de test")

    def test_declined_and_canceled(self):
        for outcome in ("declined", "canceled"):
            self.donate(500)
            donation = Donation.objects.latest("created_at")
            self.decide(donation, outcome)
            self.client.get(reverse("core:donation_return", args=[donation.reference]))
            donation.refresh_from_db()
            self.assertEqual(donation.status, outcome)

    def test_return_without_decision_stays_pending(self):
        self.donate(500)
        donation = Donation.objects.get()
        page = self.client.get(reverse("core:donation_return", args=[donation.reference]) + "?status=approved")
        donation.refresh_from_db()
        self.assertEqual(donation.status, "pending")  # le paramètre d'URL n'est jamais cru
        self.assertContains(page, "en cours de confirmation")

    def test_terminal_status_is_frozen(self):
        self.donate(500)
        donation = Donation.objects.get()
        self.decide(donation, "approved")
        self.client.get(reverse("core:donation_return", args=[donation.reference]))
        Donation.objects.filter(pk=donation.pk).update(simulated_outcome="declined")
        self.client.get(reverse("core:donation_return", args=[donation.reference]))
        donation.refresh_from_db()
        self.assertEqual(donation.status, "approved")

    def test_rate_limit(self):
        cache.clear()
        for _ in range(11):
            resp = self.client.post(reverse("core:donate"), {"amount": 500})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(Donation.objects.count(), 10)

    def test_old_confirmation_url_no_longer_claims_success(self):
        resp = self.client.get(reverse("core:donate_confirmation"))
        self.assertRedirects(resp, reverse("core:donate"))


@override_settings(PAYMENT_MODE="fedapay", FEDAPAY_SANDBOX=False, STORAGES=SIMPLE_STATIC)
class DonationFedaPayTests(TestCase):
    def make(self, **kw):
        return Donation.objects.create(amount=1000, provider="fedapay", provider_transaction_id="777",
                                       is_test=kw.pop("is_test", False), **kw)

    def test_live_fedapay_donation_is_real(self):
        self.assertFalse(donations.is_test_payment("fedapay"))

    @override_settings(FEDAPAY_SANDBOX=True)
    def test_sandbox_donation_is_test(self):
        self.assertTrue(donations.is_test_payment("fedapay"))

    def test_webhook_reverifies_with_api_and_is_idempotent(self):
        donation = self.make()
        payload = json.dumps({"id": "evt-1", "entity": {"id": 777, "status": "approved"}})
        with mock.patch("core.donations.fetch_provider_status", return_value="approved") as fetch, \
             mock.patch("payments.views.verify_fedapay_webhook_signature", return_value=True):
            for _ in range(3):
                resp = self.client.post(reverse("payments:fedapay_webhook"), payload, content_type="application/json")
                self.assertEqual(resp.status_code, 200)
        donation.refresh_from_db()
        self.assertEqual(donation.status, "approved")
        self.assertEqual(fetch.call_count, 1)  # doublons ignorés
        self.assertEqual(DonationEvent.objects.filter(event_key="webhook:evt-1").count(), 1)

    def test_webhook_payload_alone_never_confirms(self):
        donation = self.make()
        payload = json.dumps({"id": "evt-2", "entity": {"id": 777, "status": "approved"}})
        with mock.patch("core.donations.fetch_provider_status", return_value="pending"), \
             mock.patch("payments.views.verify_fedapay_webhook_signature", return_value=True):
            self.client.post(reverse("payments:fedapay_webhook"), payload, content_type="application/json")
        donation.refresh_from_db()
        self.assertEqual(donation.status, "pending")

    def test_invalid_signature_rejected(self):
        self.make()
        resp = self.client.post(reverse("core:donation_notify"), "{}", content_type="application/json",
                                HTTP_X_FEDAPAY_SIGNATURE="faux")
        self.assertEqual(resp.status_code, 403)

    def test_provider_error_keeps_pending(self):
        import requests

        donation = self.make()
        with mock.patch("core.donations.fetch_provider_status", side_effect=requests.Timeout()):
            donations.verify(donation)
        donation.refresh_from_db()
        self.assertEqual(donation.status, "pending")
        self.assertTrue(donation.last_error)


@override_settings(STORAGES=SIMPLE_STATIC)
class DonationMetricsTests(TestCase):
    def test_test_donations_never_count_as_real(self):
        from dashboard import metrics

        Donation.objects.create(amount=500, provider="simulation", status="approved", is_test=True)
        Donation.objects.create(amount=2000, provider="fedapay", status="approved", is_test=False)
        Donation.objects.create(amount=9999, provider="fedapay", status="pending", is_test=False)
        data = metrics.finance_summary()
        self.assertEqual(data["donations_real"], {"total": 2000, "count": 1})
        self.assertEqual(data["donations_test"], {"total": 500, "count": 1})
        self.assertEqual(data["real_total"], 0)  # les dons restent hors revenus de service
        admin = User.objects.create_user("admin", password="x-Pass-123", role=User.Role.ADMIN)
        self.client.force_login(admin)
        csv = self.client.get(reverse("dashboard:admin_report_export", args=["dons"])).content.decode("utf-8-sig")
        self.assertIn(";2000;", csv)
        self.assertNotIn("9999", csv)
