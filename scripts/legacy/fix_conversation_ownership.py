"""
Fix conversations where the owner doesn't match the property owner
This ensures messages are routed correctly between clients and property owners
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from messaging.models import Conversation
from properties.models import Property

print("=== Checking Conversation Ownership ===\n")

conversations = Conversation.objects.all()
print(f"Total conversations: {conversations.count()}\n")

fixed_count = 0
skipped_count = 0
error_count = 0

for conv in conversations:
    if not conv.property:
        print(f"⚠️ Skipping conversation {conv.pk} - no property linked")
        skipped_count += 1
        continue
    
    if not conv.property.owner:
        print(f"⚠️ Skipping conversation {conv.pk} - property has no owner")
        skipped_count += 1
        continue
    
    # Check if conversation owner matches property owner
    if conv.owner != conv.property.owner:
        print(f"❌ MISMATCH in conversation {conv.pk}:")
        print(f"   Property: {conv.property.title}")
        print(f"   Property owner: {conv.property.owner.username}")
        print(f"   Conversation owner: {conv.owner.username}")
        
        # Fix the conversation
        correct_owner = conv.property.owner
        old_owner = conv.owner
        
        try:
            conv.owner = correct_owner
            conv.save(update_fields=['owner'])
            print(f"✅ FIXED: Updated owner from {old_owner.username} to {correct_owner.username}")
            fixed_count += 1
        except Exception as e:
            print(f"❌ ERROR: Could not fix conversation {conv.pk}: {e}")
            error_count += 1
    else:
        skipped_count += 1

print(f"\n=== Summary ===")
print(f"Fixed: {fixed_count}")
print(f"Skipped (already correct): {skipped_count}")
print(f"Errors: {error_count}")
print(f"Total processed: {conversations.count()}")

if fixed_count > 0:
    print(f"\n✅ Successfully fixed {fixed_count} conversations")
elif error_count == 0:
    print(f"\n✅ All conversations have correct ownership")
