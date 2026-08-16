from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications.models import Notification
from .models import Property, SearchAlert


class SearchAlertNotificationsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alerteuser",
            email="alerte@example.com",
            password="testpass123",
        )

    def test_matching_property_creates_notification_for_saved_alert(self):
        alert = SearchAlert.objects.create(
            user=self.user,
            name="Villa à Lomé / budget 10 000 000",
            city="Lomé",
            property_type=Property.PropertyType.VILLA,
            transaction_type=Property.TransactionType.VENTE,
            price_max=10_000_000,
            bedrooms_min=3,
            is_active=True,
        )

        Property.objects.create(
            owner=self.user,
            title="Belle villa à Lomé",
            property_type=Property.PropertyType.VILLA,
            transaction_type=Property.TransactionType.VENTE,
            price=9_000_000,
            currency="XOF",
            country="TG",
            city="Lomé",
            bedrooms=4,
            bathrooms=3,
            surface_area=250,
            is_published=True,
            is_validated=True,
        )

        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                notification_type="info",
                title__icontains="Nouvelle propriété",
            ).exists()
        )
        alert.refresh_from_db()
        self.assertIsNotNone(alert.last_notified)
