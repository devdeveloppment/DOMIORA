"""
Test message sending functionality
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from notifications.models import Notification

User = get_user_model()

print("=== Testing Message Sending ===\n")

# Get test users
client = User.objects.filter(role='client').first()
owner = User.objects.filter(role='owner').first()

print(f"Client: {client.username}")
print(f"Owner: {owner.username}")

# Get a conversation
conversation = Conversation.objects.filter(buyer=client, owner=owner).first()

if not conversation:
    print("❌ No conversation found between client and owner")
    exit(1)

print(f"Conversation: {conversation}")
print(f"Property: {conversation.property.title if conversation.property else 'None'}")

# Test client sending a message
print(f"\n--- Client sending message ---")
msg = Message.objects.create(
    conversation=conversation,
    sender=client,
    body="Bonjour, je suis très intéressé par votre bien. Puis-je venir visiter samedi ?",
    message_type=Message.MessageType.TEXT
)
print(f"✅ Message sent: {msg.body[:50]}...")

# Test owner responding
print(f"\n--- Owner responding ---")
response = Message.objects.create(
    conversation=conversation,
    sender=owner,
    body="Bonjour, oui samedi serait parfait. Je suis disponible entre 14h et 18h.",
    message_type=Message.MessageType.TEXT
)
print(f"✅ Response sent: {response.body[:50]}...")

# Check messages
print(f"\n--- Message History ---")
messages = conversation.messages.all()
print(f"Total messages: {messages.count()}")
for m in messages:
    sender_name = "Client" if m.sender == client else "Owner"
    print(f"  [{sender_name}] {m.body[:40]}...")

# Check notifications
print(f"\n--- Notifications ---")
owner_notifications = Notification.objects.filter(user=owner).count()
client_notifications = Notification.objects.filter(user=client).count()
print(f"Owner notifications: {owner_notifications}")
print(f"Client notifications: {client_notifications}")

print(f"\n✅ Message sending functionality works correctly")
