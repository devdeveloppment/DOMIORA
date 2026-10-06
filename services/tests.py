import json
from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, override_settings
from django.test import RequestFactory

from core.views import assistant_chat
from services.ai_assistant import generate_intelligent_response


def provider_response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


@override_settings(
    MISTRAL_API_KEY="mistral-test-key",
    MISTRAL_MODEL="mistral-test-model",
    ANTHROPIC_API_KEY="",
)
class AssistantProviderTests(SimpleTestCase):
    @patch("services.ai_assistant.requests.post")
    def test_general_question_uses_mistral(self, post):
        post.return_value = provider_response({
            "choices": [{"message": {"content": "Lomé est la capitale du Togo."}}]
        })

        reply = generate_intelligent_response("Quelle est la capitale du Togo ?")

        self.assertEqual(reply, "Lomé est la capitale du Togo.")
        self.assertEqual(post.call_args.args[0], "https://api.mistral.ai/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "mistral-test-model")

    @override_settings(ANTHROPIC_API_KEY="anthropic-test-key")
    @patch("services.ai_assistant.requests.post")
    def test_anthropic_is_used_when_mistral_fails(self, post):
        post.side_effect = [
            requests.Timeout(),
            provider_response({"content": [{"type": "text", "text": "Réponse de secours."}]}),
        ]

        reply = generate_intelligent_response("Une question générale")

        self.assertEqual(reply, "Réponse de secours.")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.args[0], "https://api.anthropic.com/v1/messages")

    @override_settings(MISTRAL_API_KEY="", ANTHROPIC_API_KEY="")
    @patch("services.ai_assistant.requests.post")
    def test_local_fallback_is_used_when_no_provider_is_configured(self, post):
        reply = generate_intelligent_response("Bonjour")

        self.assertIn("Bonjour", reply)
        post.assert_not_called()


class AssistantEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.ai_assistant.get_assistant_reply")
    def test_endpoint_returns_matches_expected_by_widget(self, get_reply):
        property_match = Mock()
        property_match.title = "Appartement à Lomé"
        property_match.get_absolute_url.return_value = "/biens/appartement-lome/"
        property_match.price_display = "120 000 FCFA"
        property_match.primary_image = ""
        get_reply.return_value = {
            "reply": "Voici le bien.",
            "matches": [property_match],
            "source": "test",
        }
        request = self.factory.post(
            "/api/assistant/",
            data=json.dumps({"message": "Je cherche un appartement", "history": []}),
            content_type="application/json",
        )
        request.user = AnonymousUser()

        response = assistant_chat(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["matches"][0]["title"], "Appartement à Lomé")

    def test_endpoint_rejects_non_object_payload(self):
        request = self.factory.post("/api/assistant/", data="[]", content_type="application/json")
        request.user = AnonymousUser()

        response = assistant_chat(request)

        self.assertEqual(response.status_code, 400)