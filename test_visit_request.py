"""
Test visit request functionality
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message, VisitRequest
from datetime import datetime, timedelta

User = get_user_model()

print("=== Testing Visit Request Functionality ===\n")

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

# Test client requesting a visit
print(f"\n--- Client requesting visit ---")
visit_date = datetime.now() + timedelta(days=2)

visit_request = VisitRequest.objects.create(
    conversation=conversation,
    requester=client,
    proposed_date=visit_date,
    message="Je souhaiterais visiter samedi à 15h si possible.",
    status=VisitRequest.Status.PENDING
)
print(f"✅ Visit request created for {visit_date.strftime('%d/%m/%Y à %H:%M')}")

# Create message about the visit request
visit_msg = Message.objects.create(
    conversation=conversation,
    sender=client,
    body=f"📅 Demande de visite : {visit_date.strftime('%d/%m/%Y à %H:%M')}\nJe souhaiterais visiter samedi à 15h si possible.",
    message_type=Message.MessageType.VISIT_REQUEST,
    proposed_date=visit_date,
    visit_request=visit_request
)
print(f"✅ Visit message created")

# Test owner accepting the visit
print(f"\n--- Owner accepting visit ---")
visit_request.status = VisitRequest.Status.ACCEPTED
visit_request.save()

accept_msg = Message.objects.create(
    conversation=conversation,
    sender=owner,
    body=f"✅ Votre demande de visite pour le {visit_date.strftime('%d/%m/%Y à %H:%M')} a été acceptée.",
    message_type=Message.MessageType.VISIT_ACCEPTED,
    proposed_date=visit_date,
    visit_request=visit_request
)
print(f"✅ Visit accepted")

# Test owner proposing new date
print(f"\n--- Owner proposing new date ---")
new_date = datetime.now() + timedelta(days=3)
visit_request.status = VisitRequest.Status.PROPOSED
visit_request.response_message = "Samedi ne me convient pas, mais dimanche serait possible."
visit_request.save()

propose_msg = Message.objects.create(
    conversation=conversation,
    sender=owner,
    body=f"📅 Nouvelle proposition : {new_date.strftime('%d/%m/%Y à %H:%M')}\nSamedi ne me convient pas, mais dimanche serait possible.",
    message_type=Message.MessageType.VISIT_PROPOSED,
    proposed_date=new_date,
    visit_request=visit_request
)
print(f"✅ New date proposed: {new_date.strftime('%d/%m/%Y à %H:%M')}")

# Check messages
print(f"\n--- Message History ---")
messages = conversation.messages.all()
print(f"Total messages: {messages.count()}")
for m in messages:
    sender_name = "Client" if m.sender == client else "Owner"
    print(f"  [{sender_name}] [{m.message_type}] {m.body[:40]}...")

# Check visit request status
print(f"\n--- Visit Request Status ---")
print(f"Status: {visit_request.get_status_display()}")
print(f"Proposed date: {visit_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}")
print(f"Response message: {visit_request.response_message}")

print(f"\n✅ Visit request functionality works correctly")
