"""Tests de finalisation : frais de 500 FCFA, séparation contact/abonnements, suspension, Cloudinary privé."""
import io
import json
from unittest import mock

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from messaging.models import Conversation
from owner_subscriptions import services as subs
from owner_subscriptions.models import SubscriptionPayment
from properties.models import Property, PropertyUnlock

from .models import PaymentAttempt
from .tests import SIMPLE_STATIC, make_property

NO_NETWORK = {"post.side_effect": AssertionError("appel réseau interdit"),
              "get.side_effect": AssertionError("appel réseau interdit")}


@override_settings(STORAGES=SIMPLE_STATIC, PAYMENT_MODE="simulation", PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY=False)
class ContactFeeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.APPROVED, phone="+22891112233")
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)

    def test_fee_is_500_everywhere(self):
        self.assertEqual(settings.CONTACT_FEE_AMOUNT, 500)
        from services import assistant_knowledge
        self.assertEqual(assistant_knowledge.CONNECTION_FEE, "500 FCFA")
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(reverse("properties:payment_redirect", args=[self.prop.slug])), "500 FCFA")
        self.assertContains(self.client.get(self.prop.get_absolute_url()), "500 FCFA")
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        attempt = PaymentAttempt.objects.get()
        self.assertEqual((attempt.amount, attempt.currency), (500, "XOF"))
        self.assertContains(self.client.get(reverse("payments:simulator", args=[attempt.reference])), "500 FCFA")
        self.assertNotContains(self.client.get(self.prop.get_absolute_url()), "700 FCFA")

    def test_contact_requires_payment_on_every_entry_point(self):
        self.client.force_login(self.buyer)
        self.assertNotContains(self.client.get(self.prop.get_absolute_url()), "+22891112233")
        self.client.post(reverse("messaging:start_conversation", args=[self.owner.pk]), {"property_id": self.prop.pk, "message": "x"})
        self.client.post(reverse("rental_requests:create"), {"property_id": self.prop.pk, "request_type": "visite"})
        self.client.post(reverse("propertyrequest-list"), {"property": self.prop.pk, "request_type": "visite"})
        self.client.get(reverse("accounts:register_client_post_payment", args=[self.prop.slug]))
        self.client.get(reverse("properties:payment_confirmation", args=[self.prop.slug]) + "?status=approved&id=1")
        api = self.client.get(reverse("property-detail", args=[self.prop.slug])).content.decode()
        self.assertNotIn("+22891112233", api)
        self.assertFalse(PropertyUnlock.objects.exists())
        self.assertFalse(Conversation.objects.exists())

    def test_no_double_charge_same_owner(self):
        other = make_property(self.owner, title="Autre bien")
        self.client.force_login(self.buyer)
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        attempt = PaymentAttempt.objects.get()
        self.client.post(reverse("payments:simulator_decide", args=[attempt.reference]), {"outcome": "approved"})
        self.client.post(reverse("properties:payment_redirect", args=[other.slug]))
        self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(PropertyUnlock.objects.count(), 1)


@override_settings(STORAGES=SIMPLE_STATIC, OWNER_SUBSCRIPTIONS_ENABLED=True, PAYMENT_MODE="simulation",
                   PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY=False, FEDAPAY_SECRET_KEY="sk_live_never")
class SeparationTests(TestCase):
    def setUp(self):
        call_command("sync_subscription_plans", stdout=io.StringIO())
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.APPROVED)
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)

    def test_subscription_and_contact_payments_are_independent_and_offline(self):
        with mock.patch("payments.providers.requests", **NO_NETWORK), mock.patch("properties.fedapay.requests", **NO_NETWORK):
            sub, payment = subs.subscribe(self.owner, "premium")
            subs.decide_payment(self.owner, payment.reference, "succeeded")
            self.client.force_login(self.buyer)
            self.client.post(reverse("properties:payment_redirect", args=[self.prop.slug]))
            attempt = PaymentAttempt.objects.get()
            self.client.post(reverse("payments:simulator_decide", args=[attempt.reference]), {"outcome": "approved"})
        # L'abonnement ne crée aucune relation ni frais de contact ; le contact n'est pas un abonnement.
        self.assertEqual(SubscriptionPayment.objects.get().amount, 5000)
        self.assertEqual(PaymentAttempt.objects.get().amount, 500)
        self.assertEqual(PropertyUnlock.objects.count(), 1)
        self.assertEqual(SubscriptionPayment.objects.count(), 1)
        # Un abonnement premium du propriétaire ne dispense pas le client des frais, et inversement.
        self.assertEqual(settings.CONTACT_FEE_AMOUNT, 500)

    def test_history_amounts_never_rewritten(self):
        sub, payment = subs.subscribe(self.owner, "intermediaire")
        subs.decide_payment(self.owner, payment.reference, "succeeded")
        from owner_subscriptions.models import Plan
        Plan.objects.filter(code="intermediaire").update(price_xof=1500)
        call_command("sync_subscription_plans", stdout=io.StringIO())  # repasse à 1000 (proposition)
        payment.refresh_from_db()
        self.assertEqual(payment.amount, 1000)
        self.assertEqual(payment.environment, "demo")


@override_settings(STORAGES=SIMPLE_STATIC)
class SuspensionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("p93", password="x-Pass-123", role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.UNVERIFIED)
        self.ok_owner = User.objects.create_user("ok", password="x-Pass-123", role=User.Role.OWNER,
                                                 verification_status=User.VerificationStatus.APPROVED)
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.ok_prop = make_property(self.ok_owner, title="Bien vérifié")
        PropertyUnlock.objects.create(user=self.buyer, property=self.prop)
        self.conv = Conversation.objects.create(buyer=self.buyer, owner=self.owner, property=self.prop)

    def test_suspend_hides_publicly_keeps_everything_and_rolls_back(self):
        out = io.StringIO()
        call_command("suspend_unverified_owner_listings", stdout=out)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_published)  # simulation
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=Path(tmp) / "projet"):
            call_command("suspend_unverified_owner_listings", "--owner", str(self.owner.pk), "--apply", stdout=out)
            journal = next((Path(tmp) / "domiora_backups").glob("suspend_listings_*.json"))
            self.prop.refresh_from_db()
            self.ok_prop.refresh_from_db()
            self.assertEqual((self.prop.is_published, self.prop.is_validated), (False, True))
            self.assertTrue(self.ok_prop.is_published)
            self.assertEqual(self.client.get(self.prop.get_absolute_url()).status_code, 404)
            self.assertTrue(Property.objects.filter(pk=self.prop.pk).exists())
            self.assertTrue(PropertyUnlock.objects.filter(property=self.prop).exists())
            # Le client déjà en relation garde sa conversation.
            self.client.force_login(self.buyer)
            self.assertEqual(self.client.get(reverse("dashboard:client_conversation_detail", args=[self.conv.pk])).status_code, 200)
            # Le propriétaire non vérifié ne peut pas republier.
            self.client.force_login(self.owner)
            self.client.post(reverse("dashboard:owner_property_toggle_publish", args=[self.prop.pk]))
            self.prop.refresh_from_db()
            self.assertFalse(self.prop.is_published)
            call_command("suspend_unverified_owner_listings", "--rollback", str(journal), stdout=out)
            self.prop.refresh_from_db()
            self.assertTrue(self.prop.is_published)


class PrivateCloudinaryStorageTests(TestCase):
    """Sans identifiants réels : vérifie les appels au SDK (type authenticated, URL signée)."""

    def setUp(self):
        import cloudinary
        cloudinary.config(cloud_name="test-offline", api_key="1", api_secret="s")

    def test_upload_is_authenticated_and_no_public_url(self):
        from core.private_storage import PrivateCloudinaryStorage

        storage = PrivateCloudinaryStorage()
        with mock.patch("cloudinary.uploader.upload", return_value={"public_id": "id_documents/front/a", "format": "png"}) as up:
            name = storage.save("id_documents/front/a.png", ContentFile(b"data"))
        self.assertEqual(name, "id_documents/front/a.png")
        self.assertEqual(up.call_args.kwargs["type"], "authenticated")
        with self.assertRaises(NotImplementedError):
            storage.url(name)
        signed = storage._signed_url(name)
        self.assertIn("signature=", signed)
        self.assertIn("type=authenticated", signed)
        with mock.patch("requests.get") as get:
            get.return_value.content = b"data"
            get.return_value.raise_for_status.return_value = None
            self.assertEqual(storage.open(name).read(), b"data")
            self.assertIn("signature=", get.call_args.args[0])
