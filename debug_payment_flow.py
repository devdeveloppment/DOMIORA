"""
Debug script to check payment-to-messaging flow
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation
from properties.models import PropertyUnlock, Property

User = get_user_model()

print("=== Debug Payment Flow ===\n")

# Check users
client = User.objects.filter(role='client').first()
owner = User.objects.filter(role='owner').first()

print(f"Client: {client.username if client else 'None'}")
print(f"Owner: {owner.username if owner else 'None'}")

if not client or not owner:
    print("\n❌ Missing users")
    exit(1)

# Check property unlocks
unlocks = PropertyUnlock.objects.filter(user=client)
print(f"\nProperty unlocks for client: {unlocks.count()}")
for u in unlocks:
    print(f"  - Property: {u.property.title if u.property else 'None'}")
    print(f"    Owner: {u.property.owner.username if u.property and u.property.owner else 'None'}")

# Check conversations
convs = Conversation.objects.filter(buyer=client)
print(f"\nConversations for client: {convs.count()}")
for c in convs:
    print(f"  - Conversation: {c}")
    print(f"    Owner: {c.owner.username if c.owner else 'None'}")
    print(f"    Property: {c.property.title if c.property else 'None'}")
    print(f"    Messages: {c.messages.count()}")

# Check if there's a mismatch
print("\n=== Checking for mismatch ===")
for u in unlocks:
    if u.property:
        has_conv = Conversation.objects.filter(buyer=client, owner=u.property.owner, property=u.property).exists()
        print(f"Property: {u.property.title} - Has conversation: {has_conv}")
        if not has_conv:
            print(f"  ❌ MISSING CONVERSATION for paid property!")
            print(f"  Creating conversation now...")
            from messaging.models import Conversation, Message
            conv, created = Conversation.objects.get_or_create(
                buyer=client,
                owner=u.property.owner,
                property=u.property
            )
            if created:
                print(f"  ✓ Created conversation: {conv}")
                # Add initial message
                msg = Message.objects.create(
                    conversation=conv,
                    sender=client,
                    body=f"Bonjour, je suis intéressé par votre bien « {u.property.title} ». J'aimerais avoir plus d'informations.",
                    message_type=Message.MessageType.TEXT
                )
                print(f"  ✓ Added initial message")
            else:
                print(f"  ✓ Conversation already existed")
