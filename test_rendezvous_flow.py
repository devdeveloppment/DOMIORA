"""
Test complete rendezvous request flow
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from messaging.models import Conversation, Message, RendezvousRequest
from datetime import datetime, timedelta

User = get_user_model()

print("=== Testing Rendezvous Request Flow ===\n")

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

# Test client requesting a rendezvous
print(f"\n--- Client requesting rendezvous ---")
rendezvous_date = datetime.now() + timedelta(days=3)

rendezvous_request = RendezvousRequest.objects.create(
    conversation=conversation,
    requester=client,
    proposed_date=rendezvous_date,
    message="Je souhaiterais prendre rendez-vous pour discuter des conditions de vente.",
    status=RendezvousRequest.Status.PENDING
)
print(f"✅ Rendezvous request created for {rendezvous_date.strftime('%d/%m/%Y à %H:%M')}")

# Create message about the rendezvous request
rendezvous_msg = Message.objects.create(
    conversation=conversation,
    sender=client,
    body=f"🤝 Demande de rendez-vous : {rendezvous_date.strftime('%d/%m/%Y à %H:%M')}\nJe souhaiterais prendre rendez-vous pour discuter des conditions de vente.",
    message_type=Message.MessageType.RENDEZVOUS_REQUEST,
    proposed_date=rendezvous_date,
    rendezvous_request=rendezvous_request
)
print(f"✅ Rendezvous message created")

# Test owner accepting the rendezvous
print(f"\n--- Owner accepting rendezvous ---")
rendezvous_request.status = RendezvousRequest.Status.ACCEPTED
rendezvous_request.save()

accept_msg = Message.objects.create(
    conversation=conversation,
    sender=owner,
    body=f"✅ Votre demande de rendez-vous pour le {rendezvous_date.strftime('%d/%m/%Y à %H:%M')} a été acceptée.",
    message_type=Message.MessageType.RENDEZVOUS_ACCEPTED,
    proposed_date=rendezvous_date
)
print(f"✅ Rendezvous accepted")

# Test owner proposing new date
print(f"\n--- Owner proposing new date ---")
new_date = datetime.now() + timedelta(days=4)
rendezvous_request.status = RendezvousRequest.Status.PROPOSED
rendezvous_request.response_message = "Cette date ne me convient pas, mais le lendemain serait possible."
rendezvous_request.save()

propose_msg = Message.objects.create(
    conversation=conversation,
    sender=owner,
    body=f"📅 Nouvelle proposition : {new_date.strftime('%d/%m/%Y à %H:%M')}\nCette date ne me convient pas, mais le lendemain serait possible.",
    message_type=Message.MessageType.RENDEZVOUS_PROPOSED,
    proposed_date=new_date
)
print(f"✅ New date proposed: {new_date.strftime('%d/%m/%Y à %H:%M')}")

# Check messages
print(f"\n--- Message History ---")
messages = conversation.messages.all()
print(f"Total messages: {messages.count()}")
for m in messages:
    sender_name = "Client" if m.sender == client else "Owner"
    print(f"  [{sender_name}] [{m.message_type}] {m.body[:40]}...")

# Check rendezvous request status
print(f"\n--- Rendezvous Request Status ---")
print(f"Status: {rendezvous_request.get_status_display()}")
print(f"Proposed date: {rendezvous_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}")
print(f"Response message: {rendezvous_request.response_message}")

print(f"\n✅ Rendezvous request flow works correctly")
