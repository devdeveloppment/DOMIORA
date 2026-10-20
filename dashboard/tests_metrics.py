"""Indicateurs des tableaux de bord : calculés depuis la base, tests séparés des revenus réels."""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from owner_subscriptions.models import OwnerSubscription, Plan, SubscriptionPayment
from payments.models import PaymentAttempt
from payments.services import is_test_payment
from payments.tests import SIMPLE_STATIC, make_property

from . import metrics


def pay(client, owner, prop, amount=500, is_test=True, status=PaymentAttempt.Status.APPROVED, provider="simulation"):
    return PaymentAttempt.objects.create(
        client=client, owner=owner, property=prop, provider=provider, amount=amount,
        status=status, is_test=is_test, confirmed_at=timezone.now(),
    )


@override_settings(STORAGES=SIMPLE_STATIC)
class FinanceMetricsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.other_owner = User.objects.create_user("proprio2", password="x-Pass-123", role=User.Role.OWNER)
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.admin = User.objects.create_user("admin", password="x-Pass-123", role=User.Role.ADMIN)
        self.prop = make_property(self.owner)
        self.prop2 = make_property(self.other_owner, title="Appartement à Bè")

    def test_test_payments_never_count_as_real_revenue(self):
        pay(self.buyer, self.owner, self.prop, 500, is_test=True)
        pay(self.buyer, self.other_owner, self.prop2, 500, is_test=False, provider="fedapay")
        data = metrics.finance_summary()
        self.assertEqual(data["real_total"], 500)
        self.assertEqual(data["test_total"], 500)
        self.assertEqual(data["contact_real"]["count"], 1)

    def test_unpaid_attempts_are_ignored(self):
        for status in [PaymentAttempt.Status.PENDING, PaymentAttempt.Status.DECLINED, PaymentAttempt.Status.FAILED]:
            pay(self.buyer, self.owner, self.prop, 500, is_test=False, status=status, provider="fedapay")
        data = metrics.finance_summary()
        self.assertEqual(data["real_total"] + data["test_total"], 0)

    def test_simulated_subscriptions_are_test_revenue(self):
        plan = Plan.objects.create(code="pro-test", name="Pro", price_xof=5000)
        sub = OwnerSubscription.objects.create(owner=self.owner, plan=plan, status="active")
        SubscriptionPayment.objects.create(subscription=sub, owner=self.owner, plan=plan, amount=5000,
                                           status=SubscriptionPayment.Status.SUCCEEDED, decided_at=timezone.now())
        data = metrics.finance_summary()
        self.assertEqual(data["subs_test"]["total"], 5000)
        self.assertEqual(data["real_total"], 0)

    def test_owner_scope_only_counts_own_payments(self):
        pay(self.buyer, self.owner, self.prop, 500)
        pay(self.buyer, self.other_owner, self.prop2, 700)
        self.assertEqual(metrics.finance_summary(owner=self.owner)["test_total"], 500)

    def test_monthly_series_matches_summary(self):
        pay(self.buyer, self.owner, self.prop, 500, is_test=True)
        pay(self.buyer, self.other_owner, self.prop2, 800, is_test=False, provider="fedapay")
        series = metrics.monthly_revenue(6)
        self.assertEqual(len(series["labels"]), 6)
        self.assertEqual(sum(series["real"]), metrics.finance_summary()["real_total"])
        self.assertEqual(sum(series["test"]), metrics.finance_summary()["test_total"])

    def test_old_payments_excluded_from_period(self):
        old = pay(self.buyer, self.owner, self.prop, 500)
        PaymentAttempt.objects.filter(pk=old.pk).update(confirmed_at=timezone.now() - timezone.timedelta(days=60))
        _, _, start = metrics.resolve_period("30j")
        self.assertEqual(metrics.finance_summary(start)["test_total"], 0)
        self.assertEqual(metrics.finance_summary()["test_total"], 500)

    @override_settings(FEDAPAY_SANDBOX=True)
    def test_fedapay_sandbox_is_test(self):
        self.assertTrue(is_test_payment("fedapay"))
        self.assertTrue(is_test_payment("simulation"))

    @override_settings(FEDAPAY_SANDBOX=False)
    def test_fedapay_live_is_real(self):
        self.assertFalse(is_test_payment("fedapay"))
        self.assertTrue(is_test_payment("simulation"))

    def test_admin_pages_render_with_period(self):
        pay(self.buyer, self.owner, self.prop, 500)
        self.client.force_login(self.admin)
        for name in ["dashboard:admin_overview", "dashboard:admin_finances"]:
            for period in ["30j", "tout", "invalide"]:
                resp = self.client.get(reverse(name), {"periode": period})
                self.assertEqual(resp.status_code, 200, (name, period))
        resp = self.client.get(reverse("dashboard:admin_finances"))
        self.assertContains(resp, "Montants de test")
        self.assertEqual(resp.context["finance"]["test_total"], 500)
        self.assertEqual(resp.context["finance"]["real_total"], 0)

    def test_admin_pages_forbidden_to_others(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse("dashboard:admin_finances"))
        self.assertNotEqual(resp.status_code, 200)


@override_settings(STORAGES=SIMPLE_STATIC)
class RoleDashboardTests(TestCase):
    def setUp(self):
        from favorites.models import Favorite
        from properties.models import PropertyUnlock, PropertyView

        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.other = User.objects.create_user("autre", password="x-Pass-123", role=User.Role.OWNER)
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        self.other_prop = make_property(self.other, title="Bien d'un autre")
        PropertyView.objects.create(property=self.prop, user=self.buyer)
        PropertyView.objects.create(property=self.other_prop, user=self.buyer)
        Favorite.objects.create(user=self.buyer, property=self.prop)
        PropertyUnlock.objects.create(user=self.buyer, property=self.prop)
        pay(self.buyer, self.owner, self.prop, 500)

    def test_owner_stats_only_own_properties(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse("dashboard:owner_stats"), {"periode": "tout"})
        self.assertEqual(resp.status_code, 200)
        titles = [r["property"].title for r in resp.context["rows"]]
        self.assertEqual(titles, [self.prop.title])
        self.assertEqual(resp.context["totals"], {"views": 1, "favorites": 1, "relations": 1, "conversations": 0})
        self.assertNotContains(resp, "Bien d'un autre")

    def test_owner_overview_chart_is_real(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse("dashboard:owner_overview"))
        self.assertEqual(resp.status_code, 200)
        chart = resp.context["chart"]
        self.assertEqual(len(chart["labels"]), 6)
        self.assertEqual(sum(chart["views"]), 1)
        self.assertEqual(sum(chart["favorites"]), 1)
        self.assertNotContains(resp, "+12%")

    def test_client_overview_shows_own_data_only(self):
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse("dashboard:client_overview"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["unlocked_count"], 1)
        self.assertEqual(len(resp.context["recent_payments"]), 1)
        self.assertNotContains(resp, "Terrain à Agoè")


@override_settings(STORAGES=SIMPLE_STATIC)
class AdminStatsReportsTests(TestCase):
    def setUp(self):
        from properties.models import PropertyView

        self.admin = User.objects.create_user("admin", password="x-Pass-123", role=User.Role.ADMIN)
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              email="proprio@prive.example", phone="+22890001122")
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        for _ in range(3):
            PropertyView.objects.create(property=self.prop, user=self.buyer)
        pay(self.buyer, self.owner, self.prop, 500, is_test=True)
        self.client.force_login(self.admin)

    def test_stats_page_uses_recorded_views(self):
        resp = self.client.get(reverse("dashboard:admin_stats"), {"periode": "tout"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["funnel"][0]["count"], 3)
        self.assertEqual(resp.context["top_properties"][0]["views"], 3)

    def test_payment_export_marks_test_rows(self):
        resp = self.client.get(reverse("dashboard:admin_report_export", args=["paiements"]), {"periode": "tout"})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8-sig")
        self.assertIn("Nature", content.splitlines()[0])
        self.assertIn(";Test", content)

    def test_user_export_contains_no_contact_details(self):
        content = self.client.get(reverse("dashboard:admin_report_export", args=["utilisateurs"])).content.decode("utf-8-sig")
        self.assertIn("proprio", content)
        self.assertNotIn("@prive.example", content)
        self.assertNotIn("+22890001122", content)

    def test_unknown_report_and_non_admin_refused(self):
        self.assertEqual(self.client.get(reverse("dashboard:admin_report_export", args=["secret"])).status_code, 404)
        self.client.force_login(self.owner)
        resp = self.client.get(reverse("dashboard:admin_report_export", args=["paiements"]))
        self.assertNotEqual(resp.status_code, 200)
