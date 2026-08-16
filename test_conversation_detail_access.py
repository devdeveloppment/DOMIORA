"""
Test accessing the conversation detail page
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory, Client
from messaging.models import Conversation
from dashboard.views_client import client_conversation_detail

User = get_user_model()

print("=== Testing Conversation Detail Page Access ===\n")

# Get the specific user having issues
client = User.objects.filter(email='emmnueldev@gmail.com').first()
if not client:
    print("❌ User not found")
    exit(1)
print(f"Client: {client.username}")

# Get a conversation for this user
conversation = Conversation.objects.filter(buyer=client).first()
if not conversation:
    print("❌ No conversation found for client")
    exit(1)

print(f"Conversation ID: {conversation.pk}")
print(f"URL: /dashboard/client/messagerie/{conversation.pk}/")

# Test with Django test client
test_client = Client()
test_client.force_login(client)

# Try to access the conversation detail page
response = test_client.get(f'/dashboard/client/messagerie/{conversation.pk}/')
print(f"Response status: {response.status_code}")

if response.status_code == 200:
    print("✅ Page accessible")
    
    # Check if form is in the response
    content = response.content.decode('utf-8')
    
    if 'form' in content.lower():
        print("✅ Form found in response")
    else:
        print("❌ Form NOT found in response")
    
    if 'Écrivez votre message' in content or 'placeholder' in content.lower():
        print("✅ Placeholder found")
    else:
        print("❌ Placeholder NOT found")
    
    if 'Envoyer' in content:
        print("✅ Send button found")
    else:
        print("❌ Send button NOT found")
    
    # Check for textarea
    if 'textarea' in content.lower():
        print("✅ Textarea found")
    else:
        print("❌ Textarea NOT found")
    
    # Check for input field
    if 'input' in content.lower() or 'body' in content.lower():
        print("✅ Input field found")
    else:
        print("❌ Input field NOT found")
        
else:
    print(f"❌ Page not accessible (status: {response.status_code})")

print(f"\n=== Testing with actual view ===")

# Test the view directly
factory = RequestFactory()
request = factory.get(f'/dashboard/client/messagerie/{conversation.pk}/')
request.user = client

try:
    response = client_conversation_detail(request, conversation.pk)
    print(f"View response status: {response.status_code}")
    
    if hasattr(response, 'context_data'):
        context = response.context_data
        if 'form' in context:
            print("✅ Form in context")
            print(f"   Form type: {type(context['form'])}")
        else:
            print("❌ Form NOT in context")
            
        if 'conversation' in context:
            print("✅ Conversation in context")
        else:
            print("❌ Conversation NOT in context")
            
except Exception as e:
    print(f"❌ Error calling view: {e}")
    import traceback
    traceback.print_exc()
