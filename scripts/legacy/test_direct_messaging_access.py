"""
Test direct access to messaging page
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation

User = get_user_model()

print("=== Testing Direct Messaging Access ===\n")

# Test with the user having conversations
client = User.objects.filter(email='emmnueldev@gmail.com').first()
if not client:
    print("❌ User not found")
    exit(1)

print(f"Client: {client.username}")

# Check conversations
conversations = Conversation.objects.filter(buyer=client)
print(f"Total conversations: {conversations.count()}")

if conversations.count() > 0:
    most_recent = conversations.order_by("-updated_at").first()
    print(f"Most recent conversation ID: {most_recent.pk}")
    print(f"Property: {most_recent.property.title if most_recent.property else 'None'}")
    print(f"Owner: {most_recent.owner.username if most_recent.owner else 'None'}")
    print(f"Last updated: {most_recent.updated_at}")
    
    print(f"\n✅ When user clicks 'Messagerie', they will be redirected to:")
    print(f"   /dashboard/client/messagerie/{most_recent.pk}/")
    print(f"   This page has the message input field")
else:
    print("❌ No conversations - user will see empty inbox")

print(f"\n=== Testing with Owner ===")
owner = User.objects.filter(role='owner').first()
if owner:
    print(f"Owner: {owner.username}")
    owner_convs = Conversation.objects.filter(owner=owner)
    print(f"Owner conversations: {owner_convs.count()}")
    
    if owner_convs.count() > 0:
        most_recent = owner_convs.order_by("-updated_at").first()
        print(f"Most recent conversation ID: {most_recent.pk}")
        print(f"✅ When owner clicks 'Messagerie', they will be redirected to:")
        print(f"   /dashboard/proprietaire/messagerie/{most_recent.pk}/")
