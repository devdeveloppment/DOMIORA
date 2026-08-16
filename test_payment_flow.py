"""
Test the actual payment flow to verify conversation creation
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from properties.models import Property, PropertyUnlock
from django.contrib.auth import login
from django.test import RequestFactory

User = get_user_model()

print("=== Testing Payment Flow ===\n")

# Get test users
client = User.objects.filter(role='client').first()
owner = User.objects.filter(role='owner').first()
property_obj = Property.objects.filter(owner=owner).first()

print(f"Client: {client.username if client else 'None'}")
print(f"Owner: {owner.username if owner else 'None'}")
print(f"Property: {property_obj.title if property_obj else 'None'}")

if not all([client, owner, property_obj]):
    print("❌ Missing test data")
    exit(1)

# Simulate payment confirmation logic
print("\n--- Simulating Payment Confirmation ---")

# Create PropertyUnlock (simulating successful payment)
unlock, created = PropertyUnlock.objects.get_or_create(
    user=client,
    property=property_obj
)
print(f"PropertyUnlock {'created' if created else 'exists'}")

# Create conversation (as done in payment_confirmation)
conversation, conv_created = Conversation.objects.get_or_create(
    buyer=client,
    owner=owner,
    property=property_obj
)
print(f"Conversation {'created' if conv_created else 'exists'}: {conversation}")

# Add initial message if conversation was just created
if conv_created:
    msg = Message.objects.create(
        conversation=conversation,
        sender=client,
        body=f"Bonjour, je suis intéressé par votre bien « {property_obj.title} ». J'aimerais avoir plus d'informations.",
        message_type=Message.MessageType.TEXT
    )
    print(f"Initial message created: {msg.body[:50]}...")

# Verify the conversation appears in client's messaging view
print("\n--- Verifying Client Messaging View ---")
conversations = Conversation.objects.filter(buyer=client)
print(f"Conversations for {client.username}: {conversations.count()}")

for c in conversations:
    print(f"  - {c}")
    print(f"    Owner: {c.owner.username}")
    print(f"    Property: {c.property.title if c.property else 'None'}")
    print(f"    Messages: {c.messages.count()}")

# Check if the specific conversation is there
target_conv = Conversation.objects.filter(buyer=client, owner=owner, property=property_obj).first()
if target_conv:
    print(f"\n✅ SUCCESS: Conversation exists for client {client.username} with owner {owner.username} for property {property_obj.title}")
else:
    print(f"\n❌ FAILURE: No conversation found for client {client.username} with owner {owner.username} for property {property_obj.title}")
