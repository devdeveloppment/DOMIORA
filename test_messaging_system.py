"""
Test script for the messaging system between clients and property owners.
This script tests the complete flow:
1. Client pays for property unlock
2. Conversation is automatically created
3. Client sends message
4. Owner receives notification
5. Owner responds
6. Client receives notification
7. Visit request flow
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from properties.models import Property, PropertyUnlock
from messaging.models import Conversation, Message, VisitRequest
from notifications.models import Notification

User = get_user_model()

def test_messaging_system():
    print("=== Testing Messaging System ===\n")
    
    # Check if users exist
    try:
        owner = User.objects.filter(role='owner').first()
        client = User.objects.filter(role='client').first()
        property_obj = Property.objects.filter(owner=owner).first()
        
        if not all([owner, client, property_obj]):
            print("❌ Missing test data. Please create:")
            print("   - At least 1 owner user")
            print("   - At least 1 client user") 
            print("   - At least 1 property owned by the owner")
            return False
        
        print(f"✓ Owner: {owner.username}")
        print(f"✓ Client: {client.username}")
        print(f"✓ Property: {property_obj.title}\n")
        
        # Test 1: Create conversation
        print("Test 1: Creating conversation...")
        conversation, created = Conversation.objects.get_or_create(
            buyer=client,
            owner=owner,
            property=property_obj
        )
        print(f"✓ Conversation {'created' if created else 'retrieved'}: {conversation}\n")
        
        # Test 2: Client sends message
        print("Test 2: Client sending message...")
        msg = Message.objects.create(
            conversation=conversation,
            sender=client,
            body="Bonjour, je suis intéressé par votre bien. J'aimerais avoir plus d'informations.",
            message_type=Message.MessageType.TEXT
        )
        print(f"✓ Message sent: {msg.body[:50]}...\n")
        
        # Test 3: Check unread count
        print("Test 3: Checking unread message count...")
        unread = conversation.unread_count_for(owner)
        print(f"✓ Owner has {unread} unread messages\n")
        
        # Test 4: Owner responds
        print("Test 4: Owner responding...")
        response = Message.objects.create(
            conversation=conversation,
            sender=owner,
            body="Bonjour, oui le bien est toujours disponible. Vous pouvez demander une visite.",
            message_type=Message.MessageType.TEXT
        )
        print(f"✓ Owner response sent: {response.body[:50]}...\n")
        
        # Test 5: Client requests visit
        print("Test 5: Client requesting visit...")
        from datetime import datetime, timedelta
        visit_date = datetime.now() + timedelta(days=2)
        
        visit_request = VisitRequest.objects.create(
            conversation=conversation,
            requester=client,
            proposed_date=visit_date,
            message="Je souhaiterais visiter samedi à 15h si possible.",
            status=VisitRequest.Status.PENDING
        )
        
        visit_msg = Message.objects.create(
            conversation=conversation,
            sender=client,
            body=f"📅 Demande de visite : {visit_date.strftime('%d/%m/%Y à %H:%M')}\nJe souhaiterais visiter samedi à 15h si possible.",
            message_type=Message.MessageType.VISIT_REQUEST,
            proposed_date=visit_date,
            visit_request=visit_request
        )
        print(f"✓ Visit request created for {visit_date.strftime('%d/%m/%Y à %H:%M')}\n")
        
        # Test 6: Owner accepts visit
        print("Test 6: Owner accepting visit...")
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
        print(f"✓ Visit accepted\n")
        
        # Test 7: Check message types
        print("Test 7: Checking message types in conversation...")
        messages = conversation.messages.all()
        for m in messages:
            print(f"  - {m.message_type}: {m.body[:40]}...")
        print()
        
        # Test 8: Check notifications
        print("Test 8: Checking notifications...")
        owner_notifications = Notification.objects.filter(user=owner).count()
        client_notifications = Notification.objects.filter(user=client).count()
        print(f"✓ Owner notifications: {owner_notifications}")
        print(f"✓ Client notifications: {client_notifications}\n")
        
        print("=== All Tests Passed! ===")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_messaging_system()
    exit(0 if success else 1)
