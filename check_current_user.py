"""
Check the current user and their conversations
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation

User = get_user_model()

print("=== Checking Current User Status ===\n")

# Check all users and their conversations
clients = User.objects.filter(role='client')
print(f"Total clients: {clients.count()}\n")

for client in clients:
    print(f"Client: {client.username} ({client.email})")
    convs = Conversation.objects.filter(buyer=client)
    print(f"  Conversations: {convs.count()}")
    for c in convs:
        print(f"    - ID: {c.pk}, Owner: {c.owner.username if c.owner else 'None'}, Property: {c.property.title if c.property else 'None'}")
    print()

# Check which user might be the one having issues
print("=== Likely User Having Issues ===")
# The user mentioned "emmnueldev@gmail.com" in the error
problem_user = User.objects.filter(email='emmnueldev@gmail.com').first()
if problem_user:
    print(f"User: {problem_user.username}")
    print(f"Role: {problem_user.role}")
    convs = Conversation.objects.filter(buyer=problem_user)
    print(f"Conversations: {convs.count()}")
    if convs.count() == 0:
        print("❌ This user has NO conversations - this is the problem!")
        print("   They need to pay for a property to get a conversation")
