"""
Test the complete payment flow with a new property
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from properties.models import Property, PropertyUnlock

User = get_user_model()

print("=== Testing New Payment Flow ===\n")

# Get test users
client = User.objects.filter(role='client').first()
owner = User.objects.filter(role='owner').first()

print(f"Client: {client.username}")
print(f"Owner: {owner.username}")

# Create a new property for testing
property_obj, created = Property.objects.get_or_create(
    slug='test-payment-property',
    defaults={
        'owner': owner,
        'title': 'Villa de test pour paiement',
        'description': 'Propriété de test pour vérifier le flux de paiement',
        'property_type': Property.PropertyType.VILLA,
        'transaction_type': Property.TransactionType.VENTE,
        'price': 100000000,
        'currency': 'XOF',
        'country': 'Togo',
        'city': 'Lomé',
        'bedrooms': 3,
        'bathrooms': 2,
        'surface_area': 200,
        'status': Property.Status.DISPONIBLE,
        'is_published': True,
        'is_validated': True,
        'validation_status': Property.ValidationStatus.APPROVED
    }
)

if created:
    print(f"✅ Created test property: {property_obj.title}")
else:
    print(f"ℹ️  Using existing property: {property_obj.title}")

# Simulate payment - create PropertyUnlock
unlock, unlock_created = PropertyUnlock.objects.get_or_create(
    user=client,
    property=property_obj
)

if unlock_created:
    print(f"✅ Created PropertyUnlock for {client.username}")
else:
    print(f"ℹ️  PropertyUnlock already exists")

# Simulate payment confirmation - create conversation
conversation, conv_created = Conversation.objects.get_or_create(
    buyer=client,
    owner=owner,
    property=property_obj
)

if conv_created:
    print(f"✅ Created conversation")
    # Add initial message
    msg = Message.objects.create(
        conversation=conversation,
        sender=client,
        body=f"Bonjour, je suis intéressé par votre bien « {property_obj.title} ». J'aimerais avoir plus d'informations.",
        message_type=Message.MessageType.TEXT
    )
    print(f"✅ Added initial message")
else:
    print(f"ℹ️  Conversation already exists")

# Verify the conversation appears in client's view
conversations = Conversation.objects.filter(buyer=client)
print(f"\n=== Verification ===")
print(f"Total conversations for {client.username}: {conversations.count()}")

# Check if our test conversation is there
test_conv = Conversation.objects.filter(buyer=client, owner=owner, property=property_obj).first()
if test_conv:
    print(f"✅ SUCCESS: Test conversation exists")
    print(f"   Conversation ID: {test_conv.pk}")
    print(f"   Messages: {test_conv.messages.count()}")
else:
    print(f"❌ FAILURE: Test conversation not found")

print(f"\n=== Payment Flow Test Complete ===")
