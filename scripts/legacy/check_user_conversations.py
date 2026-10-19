"""
Check which users have conversations and property unlocks
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation
from properties.models import PropertyUnlock, Property

User = get_user_model()

print("=== User Conversation Analysis ===\n")

# Get all clients
clients = User.objects.filter(role='client')
print(f"Total clients: {clients.count()}\n")

for client in clients:
    print(f"Client: {client.username} ({client.get_full_name()})")
    
    # Check property unlocks
    unlocks = PropertyUnlock.objects.filter(user=client)
    print(f"  Property unlocks: {unlocks.count()}")
    for u in unlocks:
        print(f"    - {u.property.title if u.property else 'None'}")
    
    # Check conversations
    convs = Conversation.objects.filter(buyer=client)
    print(f"  Conversations: {convs.count()}")
    for c in convs:
        print(f"    - With: {c.owner.username if c.owner else 'None'}")
        print(f"      Property: {c.property.title if c.property else 'None'}")
        print(f"      Messages: {c.messages.count()}")
    
    print()

# Check for mismatches
print("=== Checking for Mismatches ===\n")
for client in clients:
    unlocks = PropertyUnlock.objects.filter(user=client)
    for u in unlocks:
        if u.property:
            has_conv = Conversation.objects.filter(
                buyer=client, 
                owner=u.property.owner, 
                property=u.property
            ).exists()
            if not has_conv:
                print(f"❌ {client.username} has unlock for {u.property.title} but NO conversation")
