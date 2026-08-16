"""
Fix missing conversations for existing PropertyUnlock records
This script creates conversations for users who have paid for properties
but don't have corresponding conversations yet.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message
from properties.models import PropertyUnlock

User = get_user_model()

print("=== Fixing Missing Conversations ===\n")

# Get all property unlocks
unlocks = PropertyUnlock.objects.all()
print(f"Total property unlocks: {unlocks.count()}\n")

fixed_count = 0
skipped_count = 0

for unlock in unlocks:
    # Get property using property_id directly
    from properties.models import Property
    try:
        property_obj = Property.objects.get(id=unlock.property_id) if unlock.property_id else None
    except Property.DoesNotExist:
        property_obj = None
    
    if not property_obj:
        print(f"⚠️ Skipping unlock {unlock.id} - missing property (property_id: {unlock.property_id})")
        skipped_count += 1
        continue
    
    if not property_obj.owner:
        print(f"⚠️ Skipping unlock {unlock.id} - property has no owner")
        skipped_count += 1
        continue
    
    # Check if conversation already exists
    existing = Conversation.objects.filter(
        buyer=unlock.user,
        owner=unlock.property.owner,
        property=unlock.property
    ).exists()
    
    if existing:
        print(f"⏭️  Conversation already exists for {unlock.user.username} → {unlock.property.title}")
        skipped_count += 1
        continue
    
    # Create conversation
    conversation = Conversation.objects.create(
        buyer=unlock.user,
        owner=unlock.property.owner,
        property=unlock.property
    )
    
    # Add initial message
    Message.objects.create(
        conversation=conversation,
        sender=unlock.user,
        body=f"Bonjour, je suis intéressé par votre bien « {unlock.property.title} ». J'aimerais avoir plus d'informations.",
        message_type=Message.MessageType.TEXT
    )
    
    print(f"✅ Created conversation for {unlock.user.username} → {unlock.property.title}")
    fixed_count += 1

print(f"\n=== Summary ===")
print(f"Fixed: {fixed_count}")
print(f"Skipped: {skipped_count}")
print(f"Total processed: {unlocks.count()}")

if fixed_count > 0:
    print(f"\n✅ Successfully created {fixed_count} missing conversations")
else:
    print(f"\nℹ️  No conversations needed to be created")
