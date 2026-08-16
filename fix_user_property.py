"""
Fix the specific property for the user having issues
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from properties.models import PropertyUnlock, Property

User = get_user_model()

print("=== Fixing Property for User ===\n")

# Get the user having issues
user = User.objects.filter(email='emmnueldev@gmail.com').first()
if not user:
    print("❌ User not found")
    exit(1)

print(f"User: {user.username}")

# Get the property unlock
unlock = PropertyUnlock.objects.filter(user=user).first()
if not unlock:
    print("❌ No property unlock found")
    exit(1)

print(f"Property ID: {unlock.property_id}")

# Get the property
try:
    property_obj = Property.objects.get(id=unlock.property_id)
except Property.DoesNotExist:
    print("❌ Property not found")
    exit(1)

print(f"Property: {property_obj.title}")
print(f"Current owner: {property_obj.owner.username if property_obj.owner else 'None'}")

# Assign an owner if none exists
if not property_obj.owner:
    default_owner = User.objects.filter(role='owner').first()
    if default_owner:
        property_obj.owner = default_owner
        property_obj.save()
        print(f"✅ Assigned {default_owner.username} as owner")
    else:
        print("❌ No owner user found to assign")
        exit(1)

# Create conversation
existing = Conversation.objects.filter(
    buyer=user,
    owner=property_obj.owner,
    property=property_obj
).exists()

if existing:
    print("⏭️  Conversation already exists")
else:
    conversation = Conversation.objects.create(
        buyer=user,
        owner=property_obj.owner,
        property=property_obj
    )
    
    Message.objects.create(
        conversation=conversation,
        sender=user,
        body=f"Bonjour, je suis intéressé par votre bien « {property_obj.title} ». J'aimerais avoir plus d'informations.",
        message_type=Message.MessageType.TEXT
    )
    
    print(f"✅ Created conversation: {conversation.pk}")

print(f"\n=== Summary ===")
print(f"User now has {Conversation.objects.filter(buyer=user).count()} conversations")
print(f"Conversation ID: {Conversation.objects.filter(buyer=user, property=property_obj).first().pk}")
