"""Règles anti-spam et confidentialité des questions avant mise en relation."""
import re
from datetime import timedelta

from django.utils import timezone

MAX_PER_DAY = 3
MIN_LEN, MAX_LEN = 10, 500
CONTACT_PATTERNS = [
    re.compile(r"(?:\+?\d[\s.\-]?){8,}"),                      # numéros de téléphone
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),                     # e-mails
    re.compile(r"https?://|www\.|\.com\b|\.tg\b", re.I),        # liens
    re.compile(r"whats\s?app|telegram|wa\.me", re.I),           # messageries externes
]


class InquiryError(Exception):
    pass


def check_text(text):
    text = (text or "").strip()
    if not MIN_LEN <= len(text) <= MAX_LEN:
        raise InquiryError(f"Le message doit contenir entre {MIN_LEN} et {MAX_LEN} caractères.")
    if any(p.search(text) for p in CONTACT_PATTERNS):
        raise InquiryError("Les coordonnées (téléphone, e-mail, liens, messageries) ne sont échangées "
                           "qu'après la mise en relation.")
    return text


def create_inquiry(client, prop, question):
    from notifications.models import Notification
    from payments.relations import has_owner_relation

    from .models import ListingInquiry

    if client.role != "client":
        raise InquiryError("Seul un compte client peut poser une question.")
    if prop.owner_id == client.pk:
        raise InquiryError("Vous ne pouvez pas vous poser une question.")
    if has_owner_relation(client, prop.owner):
        raise InquiryError("Vous êtes déjà en relation : utilisez la messagerie.")
    question = check_text(question)
    if ListingInquiry.objects.filter(client=client, owner=prop.owner, status=ListingInquiry.Status.OPEN).exists():
        raise InquiryError("Une question à ce propriétaire attend déjà sa réponse.")
    if ListingInquiry.objects.filter(client=client, created_at__gte=timezone.now() - timedelta(days=1)).count() >= MAX_PER_DAY:
        raise InquiryError("Limite de questions atteinte pour aujourd'hui.")
    inquiry = ListingInquiry.objects.create(client=client, owner=prop.owner, property=prop, question=question)
    Notification.objects.create(user=prop.owner, title="Nouvelle question sur une annonce",
                                message=f"« {prop.title} » : {question[:100]}", notification_type="demande",
                                link="/dashboard/proprietaire/questions/")
    return inquiry


def answer_inquiry(owner, inquiry_id, answer):
    from notifications.models import Notification

    from .models import ListingInquiry

    inquiry = ListingInquiry.objects.select_related("property").filter(pk=inquiry_id, owner=owner).first()
    if inquiry is None:
        raise InquiryError("Question introuvable.")
    if inquiry.status != ListingInquiry.Status.OPEN:
        raise InquiryError("Cette question a déjà reçu une réponse.")
    inquiry.answer = check_text(answer)
    inquiry.status = ListingInquiry.Status.ANSWERED
    inquiry.answered_at = timezone.now()
    inquiry.save()
    Notification.objects.create(user=inquiry.client, title="Réponse du propriétaire",
                                message=f"« {inquiry.property.title} » : {inquiry.answer[:100]}",
                                notification_type="systeme", link="/dashboard/client/questions/")
    return inquiry
