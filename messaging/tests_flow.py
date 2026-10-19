"""Parcours de messagerie de bout en bout : envoi, réception, réponse, notifications, permissions."""
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from payments.tests import make_property
from properties.models import PropertyUnlock

from .models import Conversation, Message

SIMPLE_STATIC = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


@override_settings(STORAGES=SIMPLE_STATIC)
class MessagingFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("proprio", password="x-Pass-123", role=User.Role.OWNER)
        self.buyer = User.objects.create_user("client", password="x-Pass-123", role=User.Role.CLIENT)
        self.intruder = User.objects.create_user("intrus", password="x-Pass-123", role=User.Role.CLIENT)
        self.prop = make_property(self.owner)
        PropertyUnlock.objects.create(user=self.buyer, property=self.prop)

    def test_send_receive_reply_notify(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse("messaging:start_conversation", args=[self.owner.pk]),
                         {"property_id": self.prop.pk, "message": "Le bien est-il disponible ?"})
        conv = Conversation.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.owner, link__contains=str(conv.pk)).exists())

        # Le propriétaire voit le message non lu, l'ouvre (lu), puis répond.
        self.client.force_login(self.owner)
        state = self.client.get(reverse("messaging:conversation_state", args=[conv.pk])).json()
        self.assertEqual(state["unread"], 1)
        self.assertContains(self.client.get(reverse("dashboard:owner_conversation_detail", args=[conv.pk])),
                            "Le bien est-il disponible ?")
        self.assertEqual(self.client.get(reverse("messaging:conversation_state", args=[conv.pk])).json()["unread"], 0)
        self.client.post(reverse("dashboard:owner_conversation_detail", args=[conv.pk]), {"body": "Oui, visite samedi possible."})
        reply = Message.objects.filter(sender=self.owner).get()

        # Le client reçoit la réponse et une seule notification pour ce message.
        self.client.force_login(self.buyer)
        state = self.client.get(reverse("messaging:conversation_state", args=[conv.pk])).json()
        self.assertEqual((state["last_message_id"], state["unread"]), (reply.pk, 1))
        self.assertEqual(Notification.objects.filter(user=self.buyer, message__startswith="Oui, visite").count(), 1)
        summary = self.client.get(reverse("notifications:unread_summary")).json()
        self.assertGreaterEqual(summary["unread"], 1)
        self.assertContains(self.client.get(reverse("dashboard:client_conversation_detail", args=[conv.pk])), "Oui, visite samedi")

    def test_no_access_by_changing_identifier(self):
        conv = Conversation.objects.create(buyer=self.buyer, owner=self.owner, property=self.prop)
        Message.objects.create(conversation=conv, sender=self.buyer, body="secret")
        self.client.force_login(self.intruder)
        self.assertEqual(self.client.get(reverse("messaging:conversation_state", args=[conv.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("dashboard:client_conversation_detail", args=[conv.pk])).status_code, 404)
        resp = self.client.get(reverse("messaging:conversation_detail", args=[conv.pk]))
        self.assertNotContains(resp, "secret", status_code=resp.status_code)
        self.client.post(reverse("dashboard:client_conversation_detail", args=[conv.pk]), {"body": "pirate"})
        self.assertFalse(Message.objects.filter(body="pirate").exists())

    def test_conversation_blocked_without_relation(self):
        PropertyUnlock.objects.all().delete()
        conv = Conversation.objects.create(buyer=self.buyer, owner=self.owner, property=self.prop)
        self.client.force_login(self.buyer)
        self.client.post(reverse("dashboard:client_conversation_detail", args=[conv.pk]), {"body": "sans relation"})
        self.assertFalse(Message.objects.filter(body="sans relation").exists())

    def test_endpoints_require_login(self):
        conv = Conversation.objects.create(buyer=self.buyer, owner=self.owner, property=self.prop)
        self.assertEqual(self.client.get(reverse("messaging:conversation_state", args=[conv.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("notifications:unread_summary")).status_code, 302)
