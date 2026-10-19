from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from messaging.models import Conversation, VisitRequest
from payments.models import PaymentAttempt
from payments.tests import make_property
from properties.models import PropertyUnlock

from .models import Review

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
FORM = {"rating": 4, "title": "Bon contact", "comment": "Visite conforme."}


@override_settings(STORAGES=SIMPLE_STATIC)
class ReviewEligibilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.client_user = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.url = reverse("ratings:create", args=[self.owner.pk])
        self.client.force_login(self.client_user)

    def paid(self, provider="fedapay", status="approved"):
        PropertyUnlock.objects.get_or_create(user=self.client_user, property=self.prop)
        return PaymentAttempt.objects.create(client=self.client_user, owner=self.owner, property=self.prop, provider=provider,
                                             amount=500, status=status, relation_granted=status == "approved")

    def visit(self, status="accepted", days=-1):
        conv, _ = Conversation.objects.get_or_create(buyer=self.client_user, owner=self.owner, property=self.prop)
        VisitRequest.objects.create(conversation=conv, requester=self.client_user, status=status,
                                    proposed_date=timezone.now() + timedelta(days=days))

    def test_without_payment_refused(self):
        self.visit()
        self.client.post(self.url, FORM)
        self.assertFalse(Review.objects.exists())

    def test_legacy_unlock_without_payment_record_refused(self):
        PropertyUnlock.objects.create(user=self.client_user, property=self.prop)
        self.visit()
        self.client.post(self.url, FORM)
        self.assertFalse(Review.objects.exists())

    def test_pending_failed_canceled_refused(self):
        self.visit()
        for st in ("pending", "declined", "canceled", "failed"):
            self.paid(status=st)
            self.client.post(self.url, FORM)
        self.assertFalse(Review.objects.exists())

    def test_simulated_payment_refused_for_real_accounts(self):
        self.paid(provider="simulation")
        self.visit()
        self.client.post(self.url, FORM)
        self.assertFalse(Review.objects.exists())

    def test_paid_but_not_completed_refused(self):
        self.paid()
        self.visit(days=+3)          # visite future
        self.visit(status="refused")  # visite refusée
        self.client.post(self.url, FORM)
        self.assertFalse(Review.objects.exists())

    def test_paid_and_completed_creates_one_verified_review(self):
        payment = self.paid()
        self.visit()
        self.client.post(self.url, FORM)
        review = Review.objects.get()
        self.assertTrue(review.is_verified)
        self.assertEqual((review.payment, review.reviewer), (payment, self.client_user))
        self.client.post(self.url, {**FORM, "title": "Encore"})
        self.assertEqual(Review.objects.count(), 1)

    def test_identity_cannot_be_forged(self):
        self.paid()
        self.visit()
        other = User.objects.create_user("autre", password="x-Pass-123", role=User.Role.CLIENT)
        self.client.post(self.url, {**FORM, "reviewer": other.pk, "owner": other.pk, "is_verified": False})
        review = Review.objects.get()
        self.assertEqual((review.reviewer, review.owner, review.is_verified), (self.client_user, self.owner, True))

    def test_demo_pair_simulation_allowed(self):
        User.objects.filter(pk__in=[self.owner.pk, self.client_user.pk]).update(is_demo=True)
        self.paid(provider="simulation")
        self.visit()
        self.client.post(self.url, FORM)
        self.assertTrue(Review.objects.exists())
