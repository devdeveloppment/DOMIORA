"""Retour depuis FedaPay après annulation ou refus : page de statut affichée sans erreur."""
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from payments.models import PaymentAttempt
from payments.tests import SIMPLE_STATIC, make_property


@override_settings(PAYMENT_MODE="fedapay", STORAGES=SIMPLE_STATIC, FEDAPAY_SECRET_KEY="sk_sandbox_x")
class FedaPayReturnTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.client_user = User.objects.create_user("cli", password="x-Pass-123", role=User.Role.CLIENT)
        prop = make_property(owner)
        self.attempt = PaymentAttempt.objects.create(
            client=self.client_user, owner=owner, property=prop, provider="fedapay",
            amount=500, currency="XOF", provider_transaction_id="123", is_test=True,
        )
        self.client.force_login(self.client_user)

    def test_every_provider_outcome_renders(self):
        for outcome in ("canceled", "declined", "pending", "refunded"):
            PaymentAttempt.objects.filter(pk=self.attempt.pk).update(status=PaymentAttempt.Status.PENDING)
            with mock.patch("payments.providers.FedaPayProvider.fetch_status", return_value=outcome):
                resp = self.client.get(reverse("payments:return", args=[self.attempt.reference]) + "?id=123&status=" + outcome)
            self.assertEqual(resp.status_code, 200, outcome)
