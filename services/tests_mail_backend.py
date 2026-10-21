"""Les e-mails partent en arrière-plan : un serveur SMTP muet ne bloque pas la page."""
import threading
import time
from unittest import mock

from django.core.mail import send_mail
from django.test import SimpleTestCase, override_settings


@override_settings(EMAIL_BACKEND="services.mail_backend.BackgroundSMTPBackend")
class BackgroundMailTests(SimpleTestCase):
    def test_slow_smtp_does_not_block_and_still_delivers(self):
        sent = threading.Event()

        def slow_send(self, messages):
            time.sleep(1)
            sent.set()
            return len(messages)

        with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", slow_send):
            start = time.monotonic()
            self.assertEqual(send_mail("Objet", "Texte", "a@x.tg", ["b@x.tg"]), 1)
            self.assertLess(time.monotonic() - start, 0.5)
            self.assertTrue(sent.wait(5))

    def test_smtp_failure_is_swallowed(self):
        with mock.patch("django.core.mail.backends.smtp.EmailBackend.send_messages", side_effect=OSError):
            self.assertEqual(send_mail("Objet", "Texte", "a@x.tg", ["b@x.tg"]), 1)
