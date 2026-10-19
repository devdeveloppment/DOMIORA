from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from payments.tests import make_property
from properties.models import PropertyUnlock
from ratings.eligibility import review_eligibility

from .models import Conversation, ListingInquiry

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


@override_settings(STORAGES=SIMPLE_STATIC)
class InquiryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER,
                                              phone="+22890000000", email="proprio@exemple.tg")
        self.other_owner = User.objects.create_user("autre", password="x-Pass-123", role=User.Role.OWNER)
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner, address="Rue 12 Adidogomé")
        self.url = reverse("properties:ask_question", args=[self.prop.slug])

    def ask(self, text="Le bien est-il disponible en décembre ?"):
        return self.client.post(self.url, {"question": text})

    def test_question_answer_and_notifications_without_relation(self):
        self.client.force_login(self.buyer)
        self.ask()
        q = ListingInquiry.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.owner, link="/dashboard/proprietaire/questions/").exists())
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("dashboard:owner_inquiries")), "disponible en décembre")
        self.client.post(reverse("dashboard:owner_inquiries"), {"inquiry_id": q.pk, "answer": "Oui, à partir du 1er."})
        q.refresh_from_db()
        self.assertEqual(q.status, "answered")
        self.assertTrue(Notification.objects.filter(user=self.buyer, title="Réponse du propriétaire").exists())
        # Une seule réponse.
        self.client.post(reverse("dashboard:owner_inquiries"), {"inquiry_id": q.pk, "answer": "Autre réponse ici"})
        q.refresh_from_db()
        self.assertEqual(q.answer, "Oui, à partir du 1er.")
        # Le client voit la réponse ; aucune relation, conversation, coordonnée ni droit d'avis.
        self.client.force_login(self.buyer)
        page = self.client.get(reverse("dashboard:client_inquiries"))
        self.assertContains(page, "à partir du 1er")
        self.assertContains(page, "500 FCFA")
        self.assertFalse(PropertyUnlock.objects.exists())
        self.assertFalse(Conversation.objects.exists())
        detail = self.client.get(self.prop.get_absolute_url())
        for secret in ("+22890000000", "proprio@exemple.tg", "Rue 12 Adidogomé"):
            self.assertNotContains(detail, secret)
        self.assertIsNone(review_eligibility(self.buyer, self.owner)[0])

    def test_contact_details_blocked_both_ways(self):
        self.client.force_login(self.buyer)
        for text in ("Appelez-moi au 90 12 34 56 78", "Écrivez à moi@mail.com svp", "Voir www.site.tg merci",
                     "Mon WhatsApp est dispo"):
            self.ask(text)
        self.assertFalse(ListingInquiry.objects.exists())
        self.ask()
        q = ListingInquiry.objects.get()
        self.client.force_login(self.owner)
        self.client.post(reverse("dashboard:owner_inquiries"), {"inquiry_id": q.pk, "answer": "Appelez le +228 90000000"})
        q.refresh_from_db()
        self.assertEqual(q.status, "open")

    def test_anti_spam_limits(self):
        self.client.force_login(self.buyer)
        self.ask()
        self.ask("Deuxième question au même propriétaire ?")
        self.assertEqual(ListingInquiry.objects.count(), 1)  # une question ouverte par propriétaire
        self.ask("court")
        self.assertEqual(ListingInquiry.objects.count(), 1)
        for i in range(4):
            o = User.objects.create_user(f"o{i}", password="x-Pass-123", role=User.Role.OWNER)
            p = make_property(o, title=f"Bien {i}")
            self.client.post(reverse("properties:ask_question", args=[p.slug]), {"question": "Disponible bientôt ?"})
        self.assertEqual(ListingInquiry.objects.filter(client=self.buyer).count(), 3)  # 3 par jour

    def test_permissions(self):
        self.assertEqual(self.ask().status_code, 302)
        self.assertFalse(ListingInquiry.objects.exists())  # anonyme refusé
        self.client.force_login(self.other_owner)
        self.ask()
        self.assertFalse(ListingInquiry.objects.exists())  # un propriétaire ne questionne pas
        self.client.force_login(self.buyer)
        self.ask()
        q = ListingInquiry.objects.get()
        self.client.force_login(self.other_owner)  # pas le destinataire
        self.client.post(reverse("dashboard:owner_inquiries"), {"inquiry_id": q.pk, "answer": "Réponse pirate ici"})
        q.refresh_from_db()
        self.assertEqual(q.status, "open")
        self.assertNotContains(self.client.get(reverse("dashboard:owner_inquiries")), "disponible en décembre")

    def test_existing_relation_uses_messaging(self):
        PropertyUnlock.objects.create(user=self.buyer, property=self.prop)
        self.client.force_login(self.buyer)
        self.ask()
        self.assertFalse(ListingInquiry.objects.exists())
