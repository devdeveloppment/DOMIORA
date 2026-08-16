"""
Setup test data for messaging system testing.
Creates test users and properties.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from properties.models import Property, PropertyImage, Amenity

User = get_user_model()

def setup_test_data():
    print("=== Setting up test data ===\n")
    
    # Create test owner
    owner, created = User.objects.get_or_create(
        username='test_owner',
        defaults={
            'email': 'owner@test.com',
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'role': User.Role.OWNER,
            'is_verified_owner': True,
            'verification_status': User.VerificationStatus.APPROVED
        }
    )
    if created:
        owner.set_password('password123')
        owner.save()
        print(f"✓ Created owner: {owner.username}")
    else:
        print(f"✓ Owner exists: {owner.username}")
    
    # Create test client
    client, created = User.objects.get_or_create(
        username='test_client',
        defaults={
            'email': 'client@test.com',
            'first_name': 'Marie',
            'last_name': 'Martin',
            'role': User.Role.CLIENT
        }
    )
    if created:
        client.set_password('password123')
        client.save()
        print(f"✓ Created client: {client.username}")
    else:
        print(f"✓ Client exists: {client.username}")
    
    # Create test property
    property_obj, created = Property.objects.get_or_create(
        slug='test-villa-lome',
        defaults={
            'owner': owner,
            'title': 'Villa 4 chambres à Lomé',
            'description': 'Magnifique villa avec 4 chambres, 3 salles de bain, piscine et jardin. Située dans un quartier calme et sécurisé.',
            'property_type': Property.PropertyType.VILLA,
            'transaction_type': Property.TransactionType.VENTE,
            'price': 150000000,
            'currency': 'XOF',
            'country': 'Togo',
            'city': 'Lomé',
            'neighborhood': 'Kodjoviakopé',
            'address': '123 Rue de la Paix',
            'bedrooms': 4,
            'bathrooms': 3,
            'surface_area': 350,
            'floors': 2,
            'status': Property.Status.DISPONIBLE,
            'is_published': True,
            'is_validated': True,
            'validation_status': Property.ValidationStatus.APPROVED
        }
    )
    
    if created:
        print(f"✓ Created property: {property_obj.title}")
    else:
        print(f"✓ Property exists: {property_obj.title}")
    
    # Add some amenities
    amenities_to_add = ['Piscine', 'Jardin', 'Garage', 'Climatisation', 'Sécurité 24/7']
    for amenity_name in amenities_to_add:
        amenity, _ = Amenity.objects.get_or_create(name=amenity_name)
        property_obj.amenities.add(amenity)
    
    print(f"✓ Added {len(amenities_to_add)} amenities to property")
    
    print("\n=== Test data setup complete ===")
    print(f"Owner login: test_owner / password123")
    print(f"Client login: test_client / password123")
    print(f"Property: {property_obj.title}")

if __name__ == "__main__":
    setup_test_data()
