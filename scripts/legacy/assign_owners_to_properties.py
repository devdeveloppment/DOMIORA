"""
Assign owners to properties that have PropertyUnlock records but no owner
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from properties.models import Property, PropertyUnlock
from messaging.models import Conversation, Message

User = get_user_model()

print("=== Assigning Owners to Properties ===\n")

# Get a default owner
default_owner = User.objects.filter(role='owner').first()
if not default_owner:
    print("❌ No owner user found. Please create an owner user first.")
    exit(1)

print(f"Using default owner: {default_owner.username}\n")

# Get properties that have PropertyUnlock but no owner
unlocks = PropertyUnlock.objects.all()
print(f"Total property unlocks: {unlocks.count()}\n")

fixed_count = 0
for unlock in unlocks:
    try:
        property_obj = Property.objects.get(id=unlock.property_id) if unlock.property_id else None
    except Property.DoesNotExist:
        property_obj = None
    
    if not property_obj:
        print(f"⚠️ Skipping unlock {unlock.id} - property not found (ID: {unlock.property_id})")
        continue
    
    if not property_obj.owner:
        # Assign owner
        property_obj.owner = default_owner
        property_obj.save()
        print(f"✅ Assigned {default_owner.username} as owner of {property_obj.title}")
        fixed_count += 1
    else:
        print(f"⏭️  {property_obj.title} already has owner: {property_obj.owner.username}")

print(f"\n=== Summary ===")
print(f"Assigned owners to {fixed_count} properties")

# Now create conversations for the fixed properties
print(f"\n=== Creating Conversations ===")

conversation_count = 0
for unlock in unlocks:
    try:
        property_obj = Property.objects.get(id=unlock.property_id) if unlock.property_id else None
    except Property.DoesNotExist:
        property_obj = None
    
    if not property_obj or not property_obj.owner:
        continue
    
    # Check if conversation already exists
    existing = Conversation.objects.filter(
        buyer=unlock.user,
        owner=property_obj.owner,
        property=property_obj
    ).exists()
    
    if existing:
        continue
    
    # Create conversation
    conversation = Conversation.objects.create(
        buyer=unlock.user,
        owner=property_obj.owner,
        property=property_obj
    )
    
    # Add initial message
    Message.objects.create(
        conversation=conversation,
        sender=unlock.user,
        body=f"Bonjour, je suis intéressé par votre bien « {property_obj.title} ». J'aimerais avoir plus d'informations.",
        message_type=Message.MessageType.TEXT
    )
    
    print(f"✅ Created conversation for {unlock.user.username} → {property_obj.title}")
    conversation_count += 1

print(f"\n=== Final Summary ===")
print(f"Assigned owners: {fixed_count}")
print(f"Created conversations: {conversation_count}")
