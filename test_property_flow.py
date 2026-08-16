"""Smoke test script kept for manual verification."""

from django.conf import settings
from django.test import Client

from accounts.models import User
from properties.models import Property


def run_test():
    settings.ALLOWED_HOSTS.append("testserver")
    client = Client()

    User.objects.filter(username="test_owner").delete()
    User.objects.create_user(
        username="test_owner",
        password="password123",
        role=User.Role.OWNER,
        email="test_owner@example.com",
        verification_status=User.VerificationStatus.APPROVED,
    )

    logged_in = client.login(username="test_owner", password="password123")
    assert logged_in, "Login failed"

    post_data = {
        "title": "Superbe Villa Test",
        "description": "Description de test...",
        "price": 1500000,
        "surface_area": 250,
        "property_type": "villa",
        "transaction_type": "vente",
        "city": "Dakar",
        "address": "Quartier Test",
        "country": "SN",
        "currency": "XOF",
        "status": "disponible",
        "bedrooms": 4,
        "bathrooms": 3,
        "floors": 1,
        "is_published": "on",
    }
    response = client.post("/dashboard/proprietaire/biens/ajouter/", post_data, HTTP_HOST="testserver")
    prop = Property.objects.filter(title="Superbe Villa Test").first()
    if prop:
        print("SUCCÈS: Propriété créée!")
    else:
        print("ERREUR:", getattr(response, "context", None))


if __name__ == "__main__":
    run_test()
