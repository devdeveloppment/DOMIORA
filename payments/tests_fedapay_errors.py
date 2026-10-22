"""Création d'un paiement FedaPay : champs client sans valeur vide, erreurs journalisées sans secret."""
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from properties.fedapay import describe_fedapay_error, fedapay_customer


class CustomerPayloadTests(SimpleTestCase):
    def test_empty_fields_are_omitted(self):
        self.assertEqual(fedapay_customer("Ama", "", ""), {"firstname": "Ama"})
        self.assertEqual(fedapay_customer("", "Mensah", "a@b.tg"), {"firstname": "Client", "lastname": "Mensah", "email": "a@b.tg"})


class ErrorLoggingTests(SimpleTestCase):
    def http_error(self, status, body):
        response = requests.Response()
        response.status_code = status
        response._content = body.encode()
        return requests.HTTPError(response=response)

    def test_http_error_is_described_with_a_hint(self):
        text = describe_fedapay_error(self.http_error(401, '{"message":"Unauthenticated"}'))
        self.assertIn("HTTP 401", text)
        self.assertIn("clé refusée", text)
        self.assertIn("Unauthenticated", text)

    @override_settings(FEDAPAY_SECRET_KEY="sk_sandbox_SECRET123", FEDAPAY_SANDBOX=True)
    def test_provider_logs_the_api_answer_but_never_the_key(self):
        from payments.providers import FedaPayProvider, ProviderError

        attempt = mock.Mock(reference="ref-1", amount=500, currency="XOF")
        attempt.client = mock.Mock(first_name="Ama", last_name="", email="")
        request = mock.Mock(build_absolute_uri=lambda url: "https://x.tg" + url)
        error = self.http_error(422, '{"message":"email invalide"}')
        with mock.patch("payments.providers.requests.post", return_value=mock.Mock(raise_for_status=mock.Mock(side_effect=error))) as post, \
                mock.patch("payments.providers.reverse", return_value="/paiements/retour/ref-1/"), \
                self.assertLogs("payments.providers", level="ERROR") as logs, self.assertRaises(ProviderError):
            FedaPayProvider().start(request, attempt)
        sent = post.call_args.kwargs["json"]["customer"]
        self.assertEqual(sent, {"firstname": "Ama"})
        output = "\n".join(logs.output)
        self.assertIn("HTTP 422", output)
        self.assertIn("email invalide", output)
        self.assertNotIn("SECRET123", output)

    @override_settings(FEDAPAY_SECRET_KEY="")
    def test_missing_key_is_explicit_in_logs(self):
        from payments.providers import FedaPayProvider, ProviderError

        with self.assertLogs("payments.providers", level="ERROR") as logs, self.assertRaises(ProviderError):
            FedaPayProvider()._headers()
        self.assertIn("FEDAPAY_SECRET_KEY absente", "\n".join(logs.output))
