"""
Envoi d'e-mails en arrière-plan : une page (inscription, demande, rendez-vous...) ne doit jamais
attendre le serveur SMTP. Les messages partent dans un fil séparé, avec un délai maximal.
"""
import logging
import threading

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

logger = logging.getLogger(__name__)


class BackgroundSMTPBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        messages = list(email_messages or [])
        if not messages:
            return 0
        threading.Thread(target=self._deliver, args=(messages,), daemon=True).start()
        return len(messages)

    @staticmethod
    def _deliver(messages):
        try:
            SMTPBackend(fail_silently=False).send_messages(messages)
        except Exception as exc:  # le site continue : l'échec est seulement journalisé
            logger.warning("Envoi d'e-mail impossible (%s)", exc.__class__.__name__)
