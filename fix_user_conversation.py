"""
Fix conversation for the specific user having issues
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from properties.models import PropertyUnlock, Property

User = get_user_model()

print("=== Fixing Conversation for User ===\n")

# Get the user having issues
user = User.objects.filter(email='emmnueldev@gmail.com').first()
if not user:
    print("❌ User not found")
    exit(1)

print(f"User: {user.username}")
print(f"Role: {user.role}")

# Check if user has property unlocks
unlocks = PropertyUnlock.objects.filter(user=user)
print(f"Property unlocks: {unlocks.count()}")

if unlocks.count() == 0:
    print("❌ User has no property unlocks (hasn't paid for any property)")
    print("   They need to pay for a property first to get a conversation")
    exit(1)

# Create conversations for each property unlock
for unlock in unlocks:
    try:
        property_obj = Property.objects.get(id=unlock.property_id) if unlock.property_id else None
    except Property.DoesNotExist:
        property_obj = None
    
    if not property_obj:
        print(f"⚠️ Skipping unlock {unlock.id} - property not found")
        continue
    
    if not property_obj.owner:
        print(f"⚠️ Skipping {property_obj.title} - no owner assigned")
        continue
    
    # Check if conversation already exists
    existing = Conversation.objects.filter(
        buyer=user,
        owner=property_obj.owner,
        property=property_obj
    ).exists()
    
    if existing:
        print(f"⏭️  Conversation already exists for {property_obj.title}")
        continue
    
    # Create conversation
    conversation = Conversation.objects.create(
        buyer=user,
        owner=property_obj.owner,
        property=property_obj
    )
    
    # Add initial message
    Message.objects.create(
        conversation=conversation,
        sender=user,
        body=f"Bonjour, je suis intéressé par votre bien « {property_obj.title} ». J'aimerais avoir plus d'informations.",
        message_type=Message.MessageType.TEXT
    )
    
    print(f"✅ Created conversation for {property_obj.title}")

print(f"\n=== Summary ===")
print(f"User now has {Conversation.objects.filter(buyer=user).count()} conversations")
