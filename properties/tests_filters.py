"""Filtres de recherche (accueil, liste, API) : prix bas sans plafond, saisie tolérante, combinaisons."""
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from payments.tests import SIMPLE_STATIC, make_property

from .models import Property
from .search_params import parse_number


class ParseNumberTests(TestCase):
    def test_formats(self):
        cases = {"10000": 10000, "10 000": 10000, "10 000": 10000, "10.000": 10000, "1.250.000": 1250000,
                 "50 000 FCFA": 50000, "12,5": 12.5, "": None, "abc": None, "-5": None, "1e999": None}
        for raw, expected in cases.items():
            self.assertEqual(parse_number(raw), expected, raw)
        self.assertIsNone(parse_number("2.5", integer=True))
        self.assertEqual(parse_number("3", integer=True), 3)


@override_settings(STORAGES=SIMPLE_STATIC)
class ListingFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        cls.low = {}
        for price in (10_000, 15_000, 20_000, 30_000, 50_000):
            cls.low[price] = make_property(owner, title=f"Chambre {price}", price=price, city="Lomé",
                                           property_type=Property.PropertyType.APPARTEMENT, bedrooms=1)
        cls.house = make_property(owner, title="Villa Kara", price=250_000, city="Kara", bedrooms=4, neighborhood="Tomdè")
        cls.sale = make_property(owner, title="Villa à vendre", price=30_000_000, city="Lomé", bedrooms=5,
                                 transaction_type=Property.TransactionType.VENTE)

    def titles(self, **params):
        resp = self.client.get(reverse("properties:list"), params)
        self.assertEqual(resp.status_code, 200, params)
        return sorted(p.title for p in resp.context["page_obj"])

    def test_low_prices_are_listed_and_filterable(self):
        self.assertEqual(self.titles(price_max="20000"), ["Chambre 10000", "Chambre 15000", "Chambre 20000"])
        self.assertEqual(self.titles(price_min="10000", price_max="10000"), ["Chambre 10000"])
        self.assertEqual(self.titles(price_min="30000", price_max="50000"), ["Chambre 30000", "Chambre 50000"])

    def test_human_formats_accepted(self):
        self.assertEqual(self.titles(price_max="15 000"), ["Chambre 10000", "Chambre 15000"])
        self.assertEqual(self.titles(price_max="15.000"), ["Chambre 10000", "Chambre 15000"])

    def test_no_upper_ceiling(self):
        self.assertIn("Villa à vendre", self.titles(price_min="1000000"))

    def test_invalid_values_ignored_without_error(self):
        everything = self.titles()
        for params in ({"price_max": "abc"}, {"price_min": "-1"}, {"bedrooms": "deux"}, {"surface_min": "x"},
                       {"bathrooms": "1.5"}):
            self.assertEqual(self.titles(**params), everything, params)

    def test_empty_fields_mean_no_filter(self):
        self.assertEqual(self.titles(q="", price_min="", price_max="", type="", transaction="", bedrooms=""), self.titles())

    def test_text_search_covers_title_city_and_neighborhood(self):
        self.assertEqual(self.titles(q="kara"), ["Villa Kara"])
        self.assertEqual(self.titles(q="Tomdè"), ["Villa Kara"])
        self.assertIn("Villa à vendre", self.titles(q="villa"))

    def test_combined_filters(self):
        self.assertEqual(self.titles(transaction="location", q="lomé", price_max="20000", bedrooms="1"),
                         ["Chambre 10000", "Chambre 15000", "Chambre 20000"])
        self.assertEqual(self.titles(transaction="vente", price_max="50000"), [])
        self.assertEqual(self.titles(type="appartement", city="Kara"), [])

    def test_no_results_message(self):
        resp = self.client.get(reverse("properties:list"), {"q": "introuvable-xyz"})
        self.assertContains(resp, "Aucun bien ne correspond")

    def test_prices_not_modified(self):
        self.client.get(reverse("properties:list"), {"price_max": "15 000"})
        self.assertEqual([int(p.price) for p in Property.objects.filter(title__startswith="Chambre").order_by("price")],
                         [10_000, 15_000, 20_000, 30_000, 50_000])

    def test_home_form_sends_supported_fields(self):
        body = self.client.get(reverse("core:home")).content.decode()
        form = body.split('action="' + reverse("properties:list") + '"')[1].split("</form>")[0]
        for field in ('name="q"', 'name="type"', 'name="price_max"', 'name="transaction"'):
            self.assertIn(field, form)
        self.assertNotIn('<option value="5000000">', form)  # ancienne liste de budgets à partir de 5 M

    def test_api_price_filters(self):
        resp = self.client.get("/api/properties/", {"price_min": "10 000", "price_max": "20000"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 3)
        self.assertEqual(self.client.get("/api/properties/", {"price_max": "abc"}).json()["count"], 7)


@override_settings(STORAGES=SIMPLE_STATIC)
class MobileLayoutRegressionTests(TestCase):
    """Débordements horizontaux corrigés à 390 px (vérifiés au navigateur) : garde-fous sur le balisage."""

    def test_detail_columns_can_shrink(self):
        owner = User.objects.create_user("p", password="x-Pass-123", role=User.Role.OWNER)
        prop = make_property(owner, title="Titre volontairement très long pour vérifier le retour à la ligne sur mobile")
        body = self.client.get(prop.get_absolute_url()).content.decode()
        self.assertIn('class="lg:col-span-3 space-y-6 min-w-0"', body)
        self.assertIn('class="space-y-4 min-w-0"', body)

    def test_about_portraits_fit_small_screens(self):
        body = self.client.get(reverse("core:about")).content.decode()
        self.assertNotIn('class="flex justify-center gap-8"', body)
        self.assertIn("w-36 h-48 sm:w-56 sm:h-72", body)


@override_settings(STORAGES=SIMPLE_STATIC)
class HomeTabsTests(TestCase):
    def test_default_tab_does_not_restrict_transaction(self):
        body = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("x-data=\"{ tab: 'tous' }\"", body)
        self.assertIn('name="transaction"', body)
        hidden = body.split('name="transaction"')[1].split(">")[0]
        self.assertIn('value="" disabled', hidden)  # sans JavaScript non plus, aucune transaction imposée
