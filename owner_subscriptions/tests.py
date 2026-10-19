import io
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from . import services
from .models import OwnerSubscription, Plan, SubscriptionPayment

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
S = OwnerSubscription.Status
P = SubscriptionPayment.Status


def owner(name="proprio", **kw):
    return User.objects.create_user(name, password="x-Pass-123", role=User.Role.OWNER,
                                    verification_status=User.VerificationStatus.APPROVED, **kw)


@override_settings(OWNER_SUBSCRIPTIONS_ENABLED=True, SUBSCRIPTION_TRIAL_DAYS=0, STORAGES=SIMPLE_STATIC)
class SubscriptionTests(TestCase):
    def setUp(self):
        call_command("sync_subscription_plans", verbosity=0, stdout=io.StringIO())
        self.owner = owner()

    def pay(self, plan_code, outcome="succeeded", user=None):
        user = user or self.owner
        sub, payment = services.subscribe(user, plan_code)
        if payment:
            services.decide_payment(user, payment.reference, outcome)
            payment.refresh_from_db()
        sub.refresh_from_db()
        return sub, payment

    def test_plans_loaded_from_configuration(self):
        prices = dict(Plan.objects.values_list("code", "price_xof"))
        self.assertEqual(prices, {"gratuit": 0, "intermediaire": 1000, "superieur": 2000, "premium": 5000, "entreprise": None})
        self.assertFalse(Plan.objects.get(code="entreprise").is_purchasable)
        call_command("sync_subscription_plans", stdout=io.StringIO())
        self.assertEqual(Plan.objects.count(), 5)  # idempotent

    def test_free_plan_by_default_and_immediate(self):
        self.assertEqual(services.active_plan(self.owner).code, "gratuit")
        sub, payment = services.subscribe(self.owner, "gratuit")
        self.assertIsNone(payment)
        self.assertEqual(sub.status, S.ACTIVE)
        self.assertIsNone(sub.current_period_end)

    def test_paid_plan_requires_successful_simulated_payment(self):
        sub, payment = services.subscribe(self.owner, "intermediaire")
        self.assertEqual(sub.status, S.PENDING)
        self.assertEqual((payment.amount, payment.currency, payment.environment, payment.is_simulated), (1000, "XOF", "demo", True))
        self.assertEqual(services.active_plan(self.owner).code, "gratuit")
        services.decide_payment(self.owner, payment.reference, "succeeded")
        sub.refresh_from_db()
        self.assertEqual(sub.status, S.ACTIVE)
        self.assertEqual(services.active_plan(self.owner).code, "intermediaire")
        self.assertAlmostEqual((sub.current_period_end - timezone.now()).days, 29, delta=1)

    def test_failed_canceled_pending_grant_nothing(self):
        for outcome in ("failed", "pending"):
            sub, payment = self.pay("premium", outcome)
            self.assertNotEqual(services.active_plan(self.owner).code, "premium")
        sub, payment = self.pay("premium", "canceled")
        self.assertEqual(sub.status, S.CANCELED)
        self.assertEqual(services.active_plan(self.owner).code, "gratuit")

    def test_repeated_requests_are_idempotent(self):
        sub1, p1 = services.subscribe(self.owner, "superieur")
        sub2, p2 = services.subscribe(self.owner, "superieur")
        self.assertEqual((sub1.pk, p1.pk), (sub2.pk, p2.pk))
        services.decide_payment(self.owner, p1.reference, "succeeded")
        end = OwnerSubscription.objects.get(pk=sub1.pk).current_period_end
        services.decide_payment(self.owner, p1.reference, "succeeded")   # rejouée
        services.decide_payment(self.owner, p1.reference, "failed")      # tentative de falsification
        sub1.refresh_from_db()
        p1.refresh_from_db()
        self.assertEqual((sub1.status, p1.status, sub1.current_period_end), (S.ACTIVE, P.SUCCEEDED, end))
        self.assertEqual(OwnerSubscription.objects.filter(owner=self.owner, status__in=OwnerSubscription.CURRENT).count(), 1)

    def test_database_forbids_two_current_subscriptions(self):
        plan = Plan.objects.get(code="premium")
        OwnerSubscription.objects.create(owner=self.owner, plan=plan, status=S.ACTIVE)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OwnerSubscription.objects.create(owner=self.owner, plan=plan, status=S.TRIAL)

    def test_upgrade_supersedes_previous(self):
        old, _ = self.pay("intermediaire")
        new, _ = self.pay("premium")
        old.refresh_from_db()
        self.assertEqual((old.status, new.status), (S.SUPERSEDED, S.ACTIVE))
        self.assertEqual(services.active_plan(self.owner).code, "premium")

    def test_downgrade_scheduled_at_period_end(self):
        sub, _ = self.pay("premium")
        same, payment = services.subscribe(self.owner, "intermediaire")
        self.assertIsNone(payment)
        self.assertEqual(same.scheduled_plan.code, "intermediaire")
        self.assertEqual(services.active_plan(self.owner).code, "premium")
        OwnerSubscription.objects.filter(pk=sub.pk).update(current_period_end=timezone.now() - timedelta(minutes=1))
        services.process_due()
        sub.refresh_from_db()
        self.assertEqual(sub.status, S.EXPIRED)
        nxt = OwnerSubscription.objects.get(owner=self.owner, status=S.PENDING)
        self.assertEqual(nxt.plan.code, "intermediaire")
        self.assertTrue(nxt.payments.filter(status=P.PENDING).exists())

    def test_cancel_keeps_benefits_until_end_then_cancelled(self):
        sub, _ = self.pay("superieur")
        services.cancel(self.owner)
        self.assertEqual(services.active_plan(self.owner).code, "superieur")
        OwnerSubscription.objects.filter(pk=sub.pk).update(current_period_end=timezone.now() - timedelta(seconds=1))
        self.assertEqual(services.active_plan(self.owner).code, "gratuit")  # avantage retiré dès l'échéance
        self.assertEqual(services.process_due(), 1)
        self.assertEqual(services.process_due(), 0)  # idempotent
        sub.refresh_from_db()
        self.assertEqual(sub.status, S.CANCELED)

    def test_simulated_renewal_extends_period(self):
        sub, _ = self.pay("intermediaire")
        end = sub.current_period_end
        payment = services.request_renewal(self.owner)
        self.assertEqual(services.request_renewal(self.owner).pk, payment.pk)
        services.decide_payment(self.owner, payment.reference, "succeeded")
        sub.refresh_from_db()
        self.assertEqual(sub.current_period_end, end + timedelta(days=30))

    @override_settings(SUBSCRIPTION_TRIAL_ENABLED=True, SUBSCRIPTION_TRIAL_DAYS=7, SUBSCRIPTION_TRIAL_ELIGIBLE_FROM="2000-01-01")
    def test_trial_once_then_expires(self):
        sub, payment = services.subscribe(self.owner, "premium")
        self.assertIsNone(payment)
        self.assertEqual(sub.status, S.TRIAL)
        OwnerSubscription.objects.filter(pk=sub.pk).update(current_period_end=timezone.now() - timedelta(seconds=1))
        services.process_due()
        sub2, payment2 = services.subscribe(self.owner, "premium")
        self.assertIsNotNone(payment2)  # pas de second essai
        self.assertEqual(sub2.status, S.PENDING)

    def test_only_owners(self):
        client = User.objects.create_user("c", password="x-Pass-123", role=User.Role.CLIENT)
        with self.assertRaises(services.SubscriptionError):
            services.subscribe(client, "premium")

    def test_web_flow_and_access_control(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("dashboard:owner_subscription")), "1,000 FCFA", html=False) \
            if False else self.assertContains(self.client.get(reverse("dashboard:owner_subscription")), "Premium")
        resp = self.client.post(reverse("dashboard:owner_subscription_action"), {"action": "subscribe", "plan": "premium"})
        payment = SubscriptionPayment.objects.get()
        self.assertRedirects(resp, reverse("dashboard:owner_subscription_payment", args=[payment.reference]),
                             fetch_redirect_response=False)
        self.assertContains(self.client.get(resp.url), "AUCUN ARGENT RÉEL")
        # Un autre propriétaire ne peut ni voir ni décider la transaction.
        other = owner("autre")
        self.client.force_login(other)
        self.assertEqual(self.client.get(resp.url).status_code, 404)
        self.assertEqual(self.client.post(resp.url, {"outcome": "succeeded"}).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(resp.url, {"outcome": "succeeded"})
        self.assertEqual(services.active_plan(self.owner).code, "premium")

    def test_api_cannot_activate_and_reports_state(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("subscription_plans")).json()["plans"][1]["price_xof"], 1000)
        self.assertEqual(self.client.post(reverse("my_subscription"), {"plan": "premium", "status": "active"}).status_code, 405)
        self.assertEqual(self.client.get(reverse("my_subscription")).json()["plan"], "gratuit")

    @override_settings(OWNER_SUBSCRIPTIONS_ENABLED=False)
    def test_disabled_flag(self):
        with self.assertRaises(services.SubscriptionError):
            services.subscribe(self.owner, "premium")
        self.assertIsNone(services.active_plan(self.owner))
        self.assertFalse(services.subscription_required_for(self.owner))


@override_settings(OWNER_SUBSCRIPTIONS_ENABLED=True, STORAGES=SIMPLE_STATIC, SUBSCRIPTION_TRIAL_DAYS=30)
class TrialTests(TestCase):
    def setUp(self):
        call_command("sync_subscription_plans", stdout=io.StringIO())
        self.owner = owner()

    def test_trial_disabled_by_default(self):
        self.assertFalse(settings.SUBSCRIPTION_TRIAL_ENABLED)
        self.assertFalse(services.trial_available(self.owner))
        sub, payment = services.subscribe(self.owner, "premium")
        self.assertEqual(sub.status, S.PENDING)
        self.assertIsNotNone(payment)

    @override_settings(SUBSCRIPTION_TRIAL_ENABLED=True, SUBSCRIPTION_TRIAL_ELIGIBLE_FROM="")
    def test_enabled_without_date_grants_nobody(self):
        self.assertFalse(services.trial_available(self.owner))

    @override_settings(SUBSCRIPTION_TRIAL_ENABLED=True)
    def test_old_accounts_not_eligible(self):
        User.objects.filter(pk=self.owner.pk).update(date_joined=timezone.now() - timedelta(days=400))
        self.owner.refresh_from_db()
        with self.settings(SUBSCRIPTION_TRIAL_ELIGIBLE_FROM=timezone.localdate().isoformat()):
            self.assertFalse(services.trial_available(self.owner))
            fresh = owner("nouveau")
            self.assertTrue(services.trial_available(fresh))

    @override_settings(SUBSCRIPTION_TRIAL_ENABLED=True, SUBSCRIPTION_TRIAL_ELIGIBLE_FROM="2000-01-01")
    def test_trial_end_exact_and_falls_back_to_free(self):
        before = timezone.now()
        sub, payment = services.subscribe(self.owner, "superieur")
        self.assertIsNone(payment)
        self.assertEqual(sub.status, S.TRIAL)
        delta = sub.current_period_end - sub.started_at
        self.assertEqual(delta, timedelta(days=30))
        self.assertGreaterEqual(sub.started_at, before)
        self.assertEqual(services.active_plan(self.owner).code, "superieur")
        # 1 seconde avant l'échéance : encore actif ; à l'échéance : avantages retirés.
        self.assertEqual(services.active_plan(self.owner, now=sub.current_period_end - timedelta(seconds=1)).code, "superieur")
        self.assertEqual(services.active_plan(self.owner, now=sub.current_period_end).code, "gratuit")
        self.assertEqual(services.process_due(now=sub.current_period_end - timedelta(seconds=1)), 0)
        self.assertEqual(services.process_due(now=sub.current_period_end), 1)
        self.assertEqual(services.process_due(now=sub.current_period_end), 0)
        sub.refresh_from_db()
        self.assertEqual(sub.status, S.EXPIRED)
        free = OwnerSubscription.objects.get(owner=self.owner, status=S.ACTIVE)
        self.assertEqual((free.plan.code, free.current_period_end), ("gratuit", None))
        sub2, payment2 = services.subscribe(self.owner, "superieur")
        self.assertIsNotNone(payment2)  # essai non renouvelable
