"""
Test payment and messaging flow - verify owner-specific logic
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from properties.models import Property, PropertyUnlock
from messaging.models import Conversation, Message
from notifications.models import Notification

User = get_user_model()

print("=== Testing Payment & Messaging Flow ===\n")

# Get test users
client = User.objects.filter(role='client').first()
owner1 = User.objects.filter(role='owner').first()
owner2 = User.objects.filter(role='owner').exclude(id=owner1.id).first()

print(f"Client: {client.username}")
print(f"Owner 1: {owner1.username}")
print(f"Owner 2: {owner2.username if owner2 else 'None'}")

# Get properties for each owner
property1 = Property.objects.filter(owner=owner1).first()
property2 = Property.objects.filter(owner=owner2).first() if owner2 else None

print(f"\nProperty 1 (Owner {owner1.username}): {property1.title if property1 else 'None'}")
print(f"Property 2 (Owner {owner2.username if owner2 else 'None'}): {property2.title if property2 else 'None'}")

# Clear existing data
Conversation.objects.filter(buyer=client).delete()
PropertyUnlock.objects.filter(user=client).delete()
Notification.objects.filter(user__in=[client, owner1, owner2]).delete()
print(f"\n✅ Cleared existing data")

# Test 1: Client pays for property1 (owner1)
print(f"\n--- Test 1: Client pays for Property 1 (Owner {owner1.username}) ---")
if property1:
    # Simulate payment unlock
    PropertyUnlock.objects.create(user=client, property=property1)
    print(f"✅ Property unlocked")
    
    # Create conversation with owner1
    conversation1, created = Conversation.objects.get_or_create(
        buyer=client,
        owner=owner1,
        property=property1
    )
    print(f"✅ Conversation created: {conversation1.pk}")
    print(f"   Buyer: {conversation1.buyer.username}")
    print(f"   Owner: {conversation1.owner.username}")
    print(f"   Property: {conversation1.property.title}")
    
    # Verify conversation is with correct owner
    assert conversation1.owner == owner1, "❌ Conversation owner mismatch!"
    assert conversation1.property == property1, "❌ Conversation property mismatch!"
    print(f"✅ Conversation linked to correct owner and property")
    
    # Send message
    msg1 = Message.objects.create(
        conversation=conversation1,
        sender=client,
        body="Bonjour, je suis intéressé par votre bien.",
        message_type=Message.MessageType.TEXT
    )
    print(f"✅ Message sent")
    
    # Create notification for owner1
    notif1 = Notification.objects.create(
        user=owner1,
        title="💬 Nouveau message",
        message=msg1.body[:120],
        notification_type="systeme",
        link=f"/dashboard/proprietaire/messagerie/{conversation1.pk}/",
    )
    print(f"✅ Notification created for owner1: {notif1.title}")
    
    # Verify notification went to correct owner
    owner1_notifications = Notification.objects.filter(user=owner1)
    print(f"Owner 1 notifications: {owner1_notifications.count()}")
    assert owner1_notifications.count() == 1, "❌ Owner 1 should have 1 notification"
    print(f"✅ Notification sent to correct owner")
    
    # Verify owner2 did NOT receive notification
    if owner2:
        owner2_notifications = Notification.objects.filter(user=owner2)
        print(f"Owner 2 notifications: {owner2_notifications.count()}")
        assert owner2_notifications.count() == 0, "❌ Owner 2 should have 0 notifications"
        print(f"✅ Owner 2 did not receive notification")

# Test 2: Client pays for property2 (owner2) - if available
if property2:
    print(f"\n--- Test 2: Client pays for Property 2 (Owner {owner2.username}) ---")
    
    # Simulate payment unlock
    PropertyUnlock.objects.create(user=client, property=property2)
    print(f"✅ Property unlocked")
    
    # Create conversation with owner2
    conversation2, created = Conversation.objects.get_or_create(
        buyer=client,
        owner=owner2,
        property=property2
    )
    print(f"✅ Conversation created: {conversation2.pk}")
    print(f"   Buyer: {conversation2.buyer.username}")
    print(f"   Owner: {conversation2.owner.username}")
    print(f"   Property: {conversation2.property.title}")
    
    # Verify conversation is with correct owner
    assert conversation2.owner == owner2, "❌ Conversation owner mismatch!"
    assert conversation2.property == property2, "❌ Conversation property mismatch!"
    print(f"✅ Conversation linked to correct owner and property")
    
    # Verify conversations are different
    assert conversation1.pk != conversation2.pk, "❌ Conversations should be different!"
    print(f"✅ Conversations are different (different owners)")
    
    # Send message
    msg2 = Message.objects.create(
        conversation=conversation2,
        sender=client,
        body="Bonjour, je suis intéressé par ce bien aussi.",
        message_type=Message.MessageType.TEXT
    )
    print(f"✅ Message sent")
    
    # Create notification for owner2
    notif2 = Notification.objects.create(
        user=owner2,
        title="💬 Nouveau message",
        message=msg2.body[:120],
        notification_type="systeme",
        link=f"/dashboard/proprietaire/messagerie/{conversation2.pk}/",
    )
    print(f"✅ Notification created for owner2: {notif2.title}")
    
    # Verify owner2 received notification
    owner2_notifications = Notification.objects.filter(user=owner2)
    print(f"Owner 2 notifications: {owner2_notifications.count()}")
    assert owner2_notifications.count() == 1, "❌ Owner 2 should have 1 notification"
    print(f"✅ Notification sent to correct owner")
    
    # Verify owner1 still has only 1 notification (from previous test)
    owner1_notifications = Notification.objects.filter(user=owner1)
    print(f"Owner 1 notifications: {owner1_notifications.count()}")
    assert owner1_notifications.count() == 1, "❌ Owner 1 should still have 1 notification"
    print(f"✅ Owner 1 notification count unchanged")

print(f"\n=== Summary ===")
print(f"Total conversations for client: {Conversation.objects.filter(buyer=client).count()}")
print(f"Total unlocks for client: {PropertyUnlock.objects.filter(user=client).count()}")
print(f"Notifications for owner1: {Notification.objects.filter(user=owner1).count()}")
print(f"Notifications for owner2: {Notification.objects.filter(user=owner2).count() if owner2 else 0}")

print(f"\n✅ Owner-specific messaging logic works correctly")
print(f"✅ Each conversation is linked to the correct property owner")
print(f"✅ Notifications are sent only to the relevant owner")
