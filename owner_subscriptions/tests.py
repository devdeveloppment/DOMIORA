from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from . import services
from .models import OwnerSubscription, Plan

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
S = OwnerSubscription.Status


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.APPROVED)
        self.plan = Plan.objects.create(code="demo", name="Plan démo", period_days=30, trial_days=14)

    def test_disabled_by_default_and_never_required(self):
        self.assertFalse(settings.OWNER_SUBSCRIPTIONS_ENABLED)
        self.assertFalse(services.subscription_required_for(self.owner))

    @override_settings(OWNER_SUBSCRIPTIONS_ENABLED=True)
    def test_enabled_flag_requires_active_subscription(self):
        self.assertTrue(services.subscription_required_for(self.owner))
        services.simulate_start(self.owner, self.plan)
        self.assertFalse(services.subscription_required_for(self.owner))

    def test_full_simulated_cycle(self):
        sub = services.simulate_start(self.owner, self.plan)
        self.assertEqual(sub.status, S.TRIAL)
        self.assertTrue(sub.is_simulated)
        services.simulate_renewal(sub, success=False)
        self.assertEqual(sub.status, S.RENEWAL_FAILED)
        services.simulate_renewal(sub, success=True)
        self.assertEqual(sub.status, S.ACTIVE)
        services.simulate_cancel(sub)
        self.assertEqual(sub.status, S.CANCELED)
        with self.assertRaises(services.SubscriptionError):
            services.simulate_renewal(sub)
        self.assertEqual(sub.events.count(), 4)

    def test_expiry(self):
        sub = services.simulate_start(self.owner, self.plan)
        OwnerSubscription.objects.filter(pk=sub.pk).update(current_period_end=timezone.now() - timedelta(days=1))
        self.assertEqual(services.expire_due(), 1)
        sub.refresh_from_db()
        self.assertEqual(sub.status, S.EXPIRED)

    @override_settings(STORAGES=SIMPLE_STATIC)
    def test_existing_publication_unaffected(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse("dashboard:owner_property_create"))
        self.assertEqual(resp.status_code, 200)
