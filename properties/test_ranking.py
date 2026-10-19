import io
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from moderation.models import ListingReport
from owner_subscriptions import services as subs
from owner_subscriptions.models import OwnerSubscription
from payments.tests import make_property
from properties.models import Property

from . import ranking

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def owner(name):
    return User.objects.create_user(name, password="x-Pass-123", role=User.Role.OWNER,
                                    verification_status=User.VerificationStatus.APPROVED)


def subscribe(user, code):
    sub, payment = subs.subscribe(user, code)
    if payment:
        subs.decide_payment(user, payment.reference, "succeeded")
    return OwnerSubscription.objects.get(owner=user, status__in=OwnerSubscription.CURRENT)


@override_settings(OWNER_SUBSCRIPTIONS_ENABLED=True, STORAGES=SIMPLE_STATIC)
class RankingTests(TestCase):
    def setUp(self):
        call_command("sync_subscription_plans", stdout=io.StringIO())
        self.free, self.mid, self.top, self.prem = (owner(n) for n in ("free", "mid", "top", "prem"))
        desc = "Belle maison lumineuse " * 12
        self.p = {}
        for u in (self.free, self.mid, self.top, self.prem):
            self.p[u.username] = make_property(u, title=f"Villa {u.username}", description=desc, latitude=6.13, longitude=1.22)
        subscribe(self.mid, "intermediaire")
        subscribe(self.top, "superieur")
        subscribe(self.prem, "premium")

    def ordered(self):
        return [p.owner.username for p in ranking.rank(Property.objects.select_related("owner").prefetch_related("images"))]

    def test_higher_plan_ranks_higher_at_equal_quality(self):
        self.assertEqual(self.ordered(), ["prem", "top", "mid", "free"])

    def test_bonus_is_capped_and_relevance_wins(self):
        # Annonce premium ancienne et incomplète vs annonce gratuite récente et complète.
        weak = make_property(self.prem, title="Terrain prem", description="", latitude=None, longitude=None)
        Property.objects.filter(pk=weak.pk).update(created_at=timezone.now() - timedelta(days=90))
        items = ranking.rank(Property.objects.select_related("owner").prefetch_related("images"))
        pos = {p.pk: i for i, p in enumerate(items)}
        self.assertLess(pos[self.p["free"].pk], pos[weak.pk])
        self.assertLessEqual(next(p.rank_score for p in items if p.pk == weak.pk), 100)

    def test_free_listings_remain_listed(self):
        self.assertIn("free", self.ordered())

    def test_expiry_removes_advantage(self):
        OwnerSubscription.objects.filter(owner=self.prem).update(current_period_end=timezone.now() - timedelta(seconds=1))
        self.assertNotEqual(self.ordered()[0], "prem")
        self.assertNotIn(self.p["prem"].pk, {p.pk for p in ranking.sponsored(Property.objects.select_related("owner").prefetch_related("images"))})

    def test_sponsored_only_from_current_results_and_capped(self):
        qs = Property.objects.select_related("owner").prefetch_related("images")
        chosen = ranking.sponsored(qs)
        self.assertLessEqual(len(chosen), settings.RANKING_SPONSORED_SLOTS)
        self.assertTrue(all(p.owner.username in ("mid", "top", "prem") for p in chosen))
        only_free = ranking.sponsored(qs.filter(owner=self.free))
        self.assertEqual(only_free, [])
        self.assertEqual(ranking.sponsored(qs, slots=10).__len__(), 3)  # 1 annonce par propriétaire ici
        # Rotation stable sur la journée.
        self.assertEqual([p.pk for p in ranking.sponsored(qs)], [p.pk for p in ranking.sponsored(qs)])

    def test_unverified_or_reported_owner_not_promoted(self):
        User.objects.filter(pk=self.prem.pk).update(verification_status=User.VerificationStatus.UNVERIFIED)
        qs = Property.objects.select_related("owner").prefetch_related("images")
        self.assertNotIn(self.p["prem"].pk, {p.pk for p in ranking.sponsored(qs, slots=10)})
        reporter = User.objects.create_user("r", password="x", role=User.Role.CLIENT)
        reporter2 = User.objects.create_user("r2", password="x", role=User.Role.CLIENT)
        for r in (reporter, reporter2):
            ListingReport.objects.create(property=self.p["top"], reporter=r, reason="scam")
        self.assertNotIn(self.p["top"].pk, {p.pk for p in ranking.sponsored(qs, slots=10)})

    def test_promotion_limited_to_plan_quota(self):
        for i in range(3):
            make_property(self.mid, title=f"Autre mid {i}")
        self.assertEqual(len(ranking.promoted_property_ids_for_owner(self.mid)), 1)
        self.assertEqual(len(ranking.promoted_property_ids_for_owner(self.free)), 0)

    def test_list_view_labels_sponsored(self):
        resp = self.client.get(reverse("properties:list"))
        self.assertContains(resp, "Sponsorisé")
        self.assertEqual(resp.context["current_sort"], "recommended")
        resp = self.client.get(reverse("properties:list") + "?sort=recent")
        self.assertNotContains(resp, 'id="sponsored-title"')

    @override_settings(OWNER_SUBSCRIPTIONS_ENABLED=False)
    def test_no_promotion_when_disabled(self):
        self.assertEqual(ranking.sponsored(Property.objects.select_related("owner").prefetch_related("images")), [])


@override_settings(OWNER_SUBSCRIPTIONS_ENABLED=True, STORAGES=SIMPLE_STATIC)
class QuotaRotationTests(TestCase):
    def setUp(self):
        call_command("sync_subscription_plans", stdout=io.StringIO())
        self.owners = {}
        for code in ("intermediaire", "superieur", "premium"):
            u = owner(code)
            for i in range(7):
                make_property(u, title=f"{code} {i}", description="x" * 250)
            subscribe(u, code)
            self.owners[code] = u
        self.qs = Property.objects.select_related("owner").prefetch_related("images")

    def test_quotas_1_3_5_enforced_server_side(self):
        expected = {"intermediaire": 1, "superieur": 3, "premium": 5}
        for code, n in expected.items():
            self.assertEqual(len(ranking.promoted_property_ids_for_owner(self.owners[code])), n)
        chosen = ranking.sponsored(self.qs, slots=50)
        per_owner = {}
        for p in chosen:
            per_owner[p.owner.username] = per_owner.get(p.owner.username, 0) + 1
        self.assertEqual(per_owner, expected)

    @override_settings(SUBSCRIPTION_PLAN_PROPOSALS=[])
    def test_quota_is_configurable_in_database(self):
        from owner_subscriptions.models import Plan
        Plan.objects.filter(code="premium").update(max_promoted_listings=2)
        self.assertEqual(len(ranking.promoted_property_ids_for_owner(self.owners["premium"])), 2)

    def test_rotation_changes_with_day_and_is_stable_within_day(self):
        day1 = timezone.now().replace(hour=10)
        same_day = [p.pk for p in ranking.sponsored(self.qs, now=day1)]
        self.assertEqual(same_day, [p.pk for p in ranking.sponsored(self.qs, now=day1.replace(hour=20))])
        seen = {tuple(p.pk for p in ranking.sponsored(self.qs, now=day1 + timedelta(days=d))) for d in range(30)}
        self.assertGreater(len(seen), 1)  # rotation effective sur un mois

    def test_expired_subscription_loses_slots_and_bonus(self):
        prem = self.owners["premium"]
        OwnerSubscription.objects.filter(owner=prem).update(current_period_end=timezone.now() - timedelta(seconds=1))
        self.assertEqual(ranking.promoted_property_ids_for_owner(prem), set())
        self.assertTrue(all(p.owner_id != prem.pk for p in ranking.sponsored(self.qs, slots=50)))
        self.assertTrue(all(p.plan_level == 0 for p in ranking.rank(self.qs) if p.owner_id == prem.pk))
