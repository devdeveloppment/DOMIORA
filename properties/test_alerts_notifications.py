from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from properties.models import SearchAlert, Property
from notifications.models import Notification


User = get_user_model()


class AlertsNotificationsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.alert_user = User.objects.create_user(username="alertuser", password="pass")
        self.owner = User.objects.create_user(username="owner", password="pass", role=User.Role.OWNER)

    def test_save_search_alert_view_creates_alert(self):
        self.client.login(username="alertuser", password="pass")
        url = reverse("properties:save_search_alert")
        resp = self.client.post(url, data={
            "city": "Lomé",
            "type": "villa",
            "transaction": "vente",
            "price_min": "100000",
            "price_max": "1000000",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SearchAlert.objects.filter(user=self.alert_user, city__iexact="Lomé").exists())

    def test_property_save_notifies_matching_alert(self):
        # create an active alert for alert_user
        alert = SearchAlert.objects.create(
            user=self.alert_user,
            name="Villa à Lomé",
            city="Lomé",
            property_type="villa",
            transaction_type="vente",
            price_min=Decimal("50000"),
            price_max=Decimal("2000000"),
            is_active=True,
        )

        # ensure no notifications yet
        self.assertEqual(Notification.objects.filter(user=self.alert_user).count(), 0)

        # create a matching property (publishing and validation should trigger notifications)
        prop = Property.objects.create(
            owner=self.owner,
            title="Superbe Villa Test",
            city="Lomé",
            property_type="villa",
            transaction_type="vente",
            price=Decimal("500000"),
            is_published=True,
            is_validated=True,
        )

        # After save, a notification should exist for alert_user
        notifs = Notification.objects.filter(user=self.alert_user)
        self.assertGreaterEqual(notifs.count(), 1)
        self.assertIn("Superbe Villa Test", notifs.first().message)
