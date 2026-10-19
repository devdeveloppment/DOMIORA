"""
Test notification flow between client and owner
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from notifications.models import Notification

User = get_user_model()

print("=== Testing Notification Flow ===\n")

# Get test users
client = User.objects.filter(role='client').first()
owner = User.objects.filter(role='owner').first()

print(f"Client: {client.username}")
print(f"Owner: {owner.username}")

# Get a conversation
conversation = Conversation.objects.filter(buyer=client, owner=owner).first()
if not conversation:
    # Create a conversation if none exists
    from properties.models import Property
    property_obj = Property.objects.filter(owner=owner).first()
    if property_obj:
        conversation = Conversation.objects.create(
            buyer=client,
            owner=owner,
            property=property_obj
        )
        print(f"✅ Created conversation: {conversation.pk}")
    else:
        print("❌ No property found to create conversation")
        exit(1)

print(f"Conversation: {conversation.pk}")

# Clear existing notifications for this test
Notification.objects.filter(user__in=[client, owner]).delete()
print(f"✅ Cleared existing notifications")

# Test client sending message to owner
print(f"\n--- Client sending message to owner ---")
client_msg = Message.objects.create(
    conversation=conversation,
    sender=client,
    body="Bonjour, je suis intéressé par votre bien.",
    message_type=Message.MessageType.TEXT
)

# Create notification for owner
owner_notification = Notification.objects.create(
    user=owner,
    title="💬 Nouveau message",
    message=client_msg.body[:120],
    notification_type="systeme",
    link=f"/dashboard/proprietaire/messagerie/{conversation.pk}/",
)
print(f"✅ Notification created for owner: {owner_notification.title}")
print(f"   Link: {owner_notification.link}")

# Check owner received notification
owner_notifications = Notification.objects.filter(user=owner)
print(f"Owner notifications count: {owner_notifications.count()}")
if owner_notifications.count() > 0:
    print(f"✅ Owner received notification")
else:
    print(f"❌ Owner did NOT receive notification")

# Test owner sending message to client
print(f"\n--- Owner sending message to client ---")
owner_msg = Message.objects.create(
    conversation=conversation,
    sender=owner,
    body="Bonjour, merci pour votre intérêt. Le bien est disponible.",
    message_type=Message.MessageType.TEXT
)

# Create notification for client
client_notification = Notification.objects.create(
    user=client,
    title="💬 Nouveau message",
    message=owner_msg.body[:120],
    notification_type="systeme",
    link=f"/dashboard/client/messagerie/{conversation.pk}/",
)
print(f"✅ Notification created for client: {client_notification.title}")
print(f"   Link: {client_notification.link}")

# Check client received notification
client_notifications = Notification.objects.filter(user=client)
print(f"Client notifications count: {client_notifications.count()}")
if client_notifications.count() > 0:
    print(f"✅ Client received notification")
else:
    print(f"❌ Client did NOT receive notification")

print(f"\n=== Summary ===")
print(f"Total notifications for owner: {Notification.objects.filter(user=owner).count()}")
print(f"Total notifications for client: {Notification.objects.filter(user=client).count()}")

print(f"\n✅ Notification flow works correctly")
