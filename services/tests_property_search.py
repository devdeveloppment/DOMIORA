"""Tests du bloc B : recherche immobilière intelligente et comparaison IA."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from properties.models import Amenity, Property
from services import property_compare, property_search
from services.property_search import NO_EXACT_MESSAGE, new_state, run_conversation_turn

User = get_user_model()

NO_LLM = {"MISTRAL_API_KEY": "", "ANTHROPIC_API_KEY": ""}
# Les tests qui rendent des pages n'ont pas besoin du manifeste collectstatic.
SIMPLE_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def make_owner(username, **extra):
    defaults = {
        "role": User.Role.OWNER,
        "verification_status": User.VerificationStatus.APPROVED,
        "phone": "+22890001122",
        "email": f"{username}@prive.example",
    }
    defaults.update(extra)
    return User.objects.create_user(username=username, password="x-test-pass-123", **defaults)


def make_property(owner, title, **fields):
    defaults = {
        "property_type": Property.PropertyType.APPARTEMENT,
        "transaction_type": Property.TransactionType.LOCATION,
        "price": 100_000,
        "currency": "FCFA",
        "city": "lome",
        "bedrooms": 2,
        "is_published": True,
        "is_validated": True,
        "validation_status": Property.ValidationStatus.APPROVED,
        "status": Property.Status.DISPONIBLE,
    }
    defaults.update(fields)
    amenities = defaults.pop("amenities", [])
    prop = Property.objects.create(owner=owner, title=title, **defaults)
    for name in amenities:
        prop.amenities.add(Amenity.objects.get_or_create(name=name)[0])
    return prop


class SearchFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner("proprio")
        cls.maison = make_property(
            cls.owner, "Maison familiale à Bè", property_type=Property.PropertyType.MAISON_DE_VILLE,
            price=200_000, bedrooms=3, amenities=["Parking privé"], description="Maison dans un quartier calme.",
        )
        cls.villa = make_property(cls.owner, "Villa avec jardin", property_type=Property.PropertyType.VILLA, price=240_000, bedrooms=4, amenities=["Jardin"])
        cls.appart = make_property(cls.owner, "Appartement Tokoin", price=150_000, bedrooms=2, amenities=["Climatisation"])
        cls.appart_cher = make_property(cls.owner, "Appartement Hédzranawoé", price=180_000, bedrooms=2)
        cls.appart_kara = make_property(cls.owner, "Appartement à Kara", city="Kara", price=100_000, bedrooms=2)
        cls.terrain = make_property(cls.owner, "Terrain à vendre", property_type=Property.PropertyType.TERRAIN,
                                    transaction_type=Property.TransactionType.VENTE, price=5_000_000, bedrooms=0)

        # Biens qui ne doivent JAMAIS être proposés
        cls.not_validated = make_property(cls.owner, "Non validé", price=90_000, is_validated=False,
                                          validation_status=Property.ValidationStatus.PENDING)
        cls.unpublished = make_property(cls.owner, "Non publié", price=90_000, is_published=False)
        cls.rented = make_property(cls.owner, "Déjà loué", price=90_000, status=Property.Status.LOUE)
        unverified = make_owner("proprio_non_verifie", verification_status=User.VerificationStatus.PENDING_DOCUMENTS)
        cls.unverified_owner = make_property(unverified, "Propriétaire non vérifié", price=90_000)
        inactive = make_owner("proprio_inactif", is_active=False)
        cls.inactive_owner = make_property(inactive, "Propriétaire inactif", price=90_000)
        client = User.objects.create_user(username="client_pub", password="x-test-pass-123", role=User.Role.CLIENT)
        cls.client_owned = make_property(client, "Annonce d'un client", price=90_000)
        cls.hidden_ids = {
            cls.not_validated.pk, cls.unpublished.pk, cls.rented.pk,
            cls.unverified_owner.pk, cls.inactive_owner.pk, cls.client_owned.pk,
        }

    def setUp(self):
        cache.clear()

    def turn(self, message, state=None):
        return run_conversation_turn(state or new_state(), message, use_llm=False)

    @staticmethod
    def ids(result, key="results"):
        return [item["id"] for item in result[key]]


@override_settings(**NO_LLM)
class PropertySearchEngineTests(SearchFixtureMixin, TestCase):
    def test_city_with_accent_matches_unaccented_database_value(self):
        _, result = self.turn("Affiche les résultats : appartement à Lomé")
        self.assertIn(self.appart.pk, self.ids(result))
        self.assertNotIn(self.appart_kara.pk, self.ids(result) + self.ids(result, "alternatives"))

    def test_budget_is_applied_and_over_budget_is_only_an_alternative(self):
        _, result = self.turn("Je cherche un appartement à Lomé, 2 chambres, budget maximum 150 000 FCFA par mois")
        self.assertEqual(result["status"], "results")
        self.assertEqual(self.ids(result), [self.appart.pk])
        self.assertIn(self.appart_cher.pk, self.ids(result, "alternatives"))
        alternative = next(a for a in result["alternatives"] if a["id"] == self.appart_cher.pk)
        self.assertEqual(alternative["match_level"], "partial")
        self.assertTrue(any(r["status"] == "near" and "budget" in r["text"] for r in alternative["reasons"]))

    def test_budget_phrasings(self):
        from services.property_search import extract_rules

        cases = {
            "pas plus de 500 mille par mois": ("budget_max", 500_000),
            "maximum 150 000 FCFA": ("budget_max", 150_000),
            "150k": ("budget_max", 150_000),
            "1,5 million": ("budget_max", 1_500_000),
            "à partir de 2 millions": ("budget_min", 2_000_000),
            "pas moins de 100 000 FCFA": ("budget_min", 100_000),
        }
        for message, (key, value) in cases.items():
            delta, _ = extract_rules(message)
            self.assertEqual(delta.get(key), value, message)
        delta, _ = extract_rules("entre 100k et 200k")
        self.assertEqual((delta["budget_min"], delta["budget_max"]), (100_000, 200_000))
        self.assertNotIn("budget_max", extract_rules("villa de 300 m2, 3 chambres")[0])

    def test_far_over_budget_is_never_proposed(self):
        _, result = self.turn("maison à Lomé 3 chambres maximum 100 000 FCFA")
        proposed = self.ids(result) + self.ids(result, "alternatives")
        self.assertNotIn(self.villa.pk, proposed)

    def test_bedrooms_minimum_versus_exact(self):
        _, at_least = self.turn("Affiche les résultats : maison à Lomé au moins 3 chambres budget 300 000")
        self.assertEqual(set(self.ids(at_least)), {self.maison.pk, self.villa.pk})
        _, exact = self.turn("Affiche les résultats : maison à Lomé exactement 3 chambres budget 300 000")
        self.assertEqual(self.ids(exact), [self.maison.pk])

    def test_generic_house_maps_to_existing_property_types(self):
        _, result = self.turn("Affiche les résultats : une maison à Lomé")
        self.assertEqual(set(self.ids(result)), {self.maison.pk, self.villa.pk})

    def test_multiple_criteria_ranked_with_explanations(self):
        _, result = self.turn("Je cherche une maison à Lomé, 3 chambres, maximum 250 000 FCFA, avec parking.")
        self.assertEqual(result["status"], "results")
        self.assertEqual(self.ids(result), [self.maison.pk])
        top = result["results"][0]
        self.assertIn(top["match_level"], ("excellent", "good"))
        texts = " | ".join(r["text"] for r in top["reasons"])
        self.assertIn("Budget respecté", texts)
        self.assertIn("Parking disponible", texts)
        # La villa (sans parking indiqué) n'est qu'une alternative, avec la différence signalée.
        self.assertIn(self.villa.pk, self.ids(result, "alternatives"))
        villa = next(a for a in result["alternatives"] if a["id"] == self.villa.pk)
        self.assertTrue(any(r["status"] == "near" and "Parking" in r["text"] for r in villa["reasons"]))

    def test_no_result_says_so_clearly(self):
        _, result = self.turn("Je cherche une villa à Kara, 3 chambres, 500 000 FCFA maximum")
        self.assertEqual(result["status"], "none")
        self.assertIn(NO_EXACT_MESSAGE, result["message"])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["alternatives"], [])

    def test_close_results_are_presented_as_alternatives(self):
        _, result = self.turn("appartement à Lomé 2 chambres maximum 140 000 FCFA")
        self.assertEqual(result["status"], "no_exact")
        self.assertTrue(result["message"].startswith(NO_EXACT_MESSAGE))
        self.assertIn(self.appart.pk, self.ids(result, "alternatives"))

    def test_hidden_properties_are_never_proposed(self):
        messages = [
            "Affiche les résultats : appartement à Lomé",
            "Affiche les résultats : appartement à Lomé maximum 95 000 FCFA",
            "Affiche les résultats",
        ]
        for message in messages:
            _, result = self.turn(message)
            proposed = set(self.ids(result) + self.ids(result, "alternatives"))
            self.assertFalse(proposed & self.hidden_ids, message)

    def test_preference_not_in_listing_is_reported_not_assumed(self):
        _, result = self.turn("Je cherche un appartement à Lomé, 2 chambres, quartier calme, maximum 150 000 FCFA")
        appart = result["results"][0]
        self.assertTrue(any(r["status"] == "unknown" and "calme" in r["text"].lower() for r in appart["reasons"]))

    def test_rooms_criterion_is_flagged_as_unavailable(self):
        _, result = self.turn("appartement 3 pièces à Lomé 2 chambres maximum 200 000")
        self.assertTrue(any("pièces" in note for note in result["notes"]))


@override_settings(**NO_LLM)
class ConversationTests(SearchFixtureMixin, TestCase):
    def test_clarification_questions_then_results_then_refinement(self):
        state, r1 = self.turn("Je cherche une maison.")
        self.assertEqual(r1["status"], "question")
        self.assertEqual(r1["question_key"], "location")

        state, r2 = self.turn("Lomé", state)
        self.assertEqual(r2["question_key"], "budget")

        state, r3 = self.turn("250 000", state)
        self.assertEqual(r3["question_key"], "bedrooms")
        self.assertEqual(state["criteria"]["budget_max"], 250_000)

        state, r4 = self.turn("3", state)
        self.assertEqual(r4["status"], "results")
        self.assertEqual(set(self.ids(r4)), {self.maison.pk, self.villa.pk})

        state, r5 = self.turn("Seulement avec parking.", state)
        self.assertEqual(self.ids(r5), [self.maison.pk])
        self.assertIn("Parking", r5["criteria_summary"])
        self.assertEqual(state["last_result_ids"][0], self.maison.pk)

    def test_each_question_is_asked_only_once(self):
        state, _ = self.turn("Je cherche une maison à Lomé")
        state, second = self.turn("peu importe", state)
        self.assertEqual(second["question_key"], "bedrooms")
        state, third = self.turn("peu importe", state)
        self.assertEqual(third["status"], "results")

    def test_show_now_skips_questions(self):
        _, result = self.turn("Je cherche une maison, affiche les résultats")
        self.assertNotEqual(result["status"], "question")

    def test_new_search_resets_previous_criteria(self):
        state, _ = self.turn("Je cherche une maison à Lomé avec parking, 3 chambres, 250 000")
        state, result = self.turn("Je cherche un terrain à vendre, affiche les résultats", state)
        self.assertEqual(state["criteria"]["features"], [])
        self.assertEqual(self.ids(result), [self.terrain.pk])


class LlmExtractionTests(SearchFixtureMixin, TestCase):
    @override_settings(MISTRAL_API_KEY="test-key", ANTHROPIC_API_KEY="")
    @patch("services.llm.complete_json")
    def test_llm_output_is_validated_against_whitelists(self, complete_json):
        complete_json.return_value = (
            {
                "property_kind": "chateau_de_reve_invente",
                "city": "Lomé<script>",
                "budget_max": "150000",
                "bedrooms": 2,
                "bedrooms_mode": "exact",
                "features": ["parking", "teleporteur"],
                "preferences": ["calme", "inexistant"],
            },
            "Mistral",
        )
        state, _ = run_conversation_turn(new_state(), "requête quelconque", use_llm=True)
        criteria = state["criteria"]
        self.assertIsNone(criteria["property_kind"])
        self.assertEqual(criteria["city"], "lomescript")
        self.assertEqual(criteria["budget_max"], 150_000)
        self.assertEqual(criteria["bedrooms_mode"], "exact")
        self.assertEqual(criteria["features"], ["parking"])
        self.assertEqual(criteria["preferences"], ["calme"])

    @override_settings(MISTRAL_API_KEY="test-key", ANTHROPIC_API_KEY="")
    @patch("services.llm.complete", return_value=("", None))
    def test_provider_failure_falls_back_to_local_rules(self, _complete):
        state, result = run_conversation_turn(new_state(), "appartement à Lomé 2 chambres maximum 150 000 FCFA", use_llm=True)
        self.assertEqual(state["criteria"]["budget_max"], 150_000)
        self.assertEqual(self.ids(result), [self.appart.pk])


@override_settings(**NO_LLM, AI_RATE_LIMIT=20)
class AiSearchApiTests(SearchFixtureMixin, TestCase):
    url = reverse("properties:ai_search_api")

    def post(self, body):
        return self.client.post(self.url, data=json.dumps(body), content_type="application/json")

    @override_settings(STORAGES=SIMPLE_STATIC)
    def test_page_renders(self):
        response = self.client.get(reverse("properties:ai_search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recherche avec l")

    def test_state_is_kept_in_session_between_turns(self):
        self.assertEqual(self.post({"message": "Je cherche une maison à Lomé"}).json()["question_key"], "budget")
        self.assertEqual(self.post({"message": "250 000"}).json()["question_key"], "bedrooms")
        data = self.post({"message": "3"}).json()
        self.assertEqual(data["status"], "results")
        self.assertEqual(self.client.session["ai_search_state"]["criteria"]["budget_max"], 250_000)

    def test_reset_clears_state(self):
        self.post({"message": "Je cherche une maison à Lomé"})
        self.assertEqual(self.post({"reset": True}).json()["status"], "reset")
        self.assertIsNone(self.client.session["ai_search_state"]["criteria"]["property_kind"])

    def test_invalid_requests(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.post({"message": "   "}).status_code, 400)
        self.assertEqual(self.post({"message": "x" * 1001}).status_code, 400)

    @override_settings(AI_RATE_LIMIT=2)
    def test_rate_limit(self):
        self.assertEqual(self.post({"message": "appartement à Lomé"}).status_code, 200)
        self.assertEqual(self.post({"message": "appartement à Lomé"}).status_code, 200)
        self.assertEqual(self.post({"message": "appartement à Lomé"}).status_code, 429)

    def test_response_never_contains_private_owner_data(self):
        response = self.post({"message": "Affiche les résultats : maison à Lomé"})
        content = response.content.decode()
        self.assertNotIn("+22890001122", content)
        self.assertNotIn("@prive.example", content)
        self.assertNotIn("proprio", content)


@override_settings(**NO_LLM)
class CompareAnalysisTests(SearchFixtureMixin, TestCase):
    def test_missing_information_is_explicit(self):
        result = property_compare.compare([self.maison, self.villa], use_llm=False)
        maison_rows = dict((r["label"], r["value"]) for r in result["properties"][0]["rows"])
        self.assertEqual(maison_rows["Superficie"], property_compare.MISSING)
        self.assertEqual(maison_rows["Année de construction"], property_compare.MISSING)
        self.assertIn("Le prix le plus bas de la sélection", result["properties"][0]["pros"])
        self.assertEqual(result["source"], "local")

    def test_endpoint_respects_visibility_and_needs_two_properties(self):
        url = reverse("properties:compare_analysis")
        ok = self.client.get(url, {"ids": f"{self.maison.pk},{self.villa.pk}"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(len(ok.json()["properties"]), 2)
        hidden = self.client.get(url, {"ids": f"{self.maison.pk},{self.not_validated.pk}"})
        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(self.client.get(url, {"ids": str(self.maison.pk)}).status_code, 400)

    @override_settings(STORAGES=SIMPLE_STATIC)
    def test_compare_page_shows_ai_panel(self):
        response = self.client.get(reverse("properties:compare"), {"ids": f"{self.maison.pk},{self.villa.pk}"})
        self.assertContains(response, "Analyse IA de la comparaison")
        self.assertContains(response, "Information non renseignée")

    @override_settings(MISTRAL_API_KEY="test-key")
    @patch("services.llm.complete_json")
    def test_llm_summary_with_invented_number_is_rejected(self, complete_json):
        complete_json.return_value = ({"summary": "La maison fait 350 m² et possède une piscine."}, "Mistral")
        result = property_compare.compare([self.maison, self.villa])
        self.assertEqual(result["source"], "local")
        self.assertNotIn("350", result["summary"])

    @override_settings(MISTRAL_API_KEY="test-key")
    @patch("services.llm.complete_json")
    def test_llm_summary_grounded_in_facts_is_used(self, complete_json):
        complete_json.return_value = ({"summary": "La maison coûte 200 000 FCFA par mois, la villa offre 4 chambres."}, "Mistral")
        result = property_compare.compare([self.maison, self.villa])
        self.assertEqual(result["source"], "ai")


@override_settings(**NO_LLM)
class LegacyAssistantSearchTests(SearchFixtureMixin, TestCase):
    def test_legacy_search_excludes_hidden_and_applies_budget(self):
        from services.ai_assistant import search_properties_with_criteria

        results = list(search_properties_with_criteria({"city": "lomé", "property_type": "apartment", "budget": "150000"}))
        self.assertEqual([p.pk for p in results], [self.appart.pk])
        self.assertFalse({p.pk for p in results} & self.hidden_ids)
