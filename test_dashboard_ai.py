"""
Test AI assistant integration in dashboards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.ai_assistant import get_assistant_reply
from accounts.models import User

print("="*80)
print("TEST AI ASSISTANT INTEGRATION - DASHBOARDS")
print("="*80)

# Test 1: Unauthenticated user (visitor)
print("\n" + "="*80)
print("TEST 1: Visitor (unauthenticated)")
print("="*80)
result = get_assistant_reply("Bonjour, je cherche un appartement", user=None)
print(f"Response: {result['reply'][:200]}...")
print(f"Source: {result['source']}")
print(f"Matches: {len(result['matches'])}")

# Test 2: Owner user
print("\n" + "="*80)
print("TEST 2: Owner (authenticated)")
print("="*80)
try:
    owner_user = User.objects.filter(role='owner').first()
    if owner_user:
        result = get_assistant_reply("Comment publier une annonce ?", user=owner_user)
        print(f"Response: {result['reply'][:200]}...")
        print(f"Source: {result['source']}")
        print(f"Matches: {len(result['matches'])}")
    else:
        print("No owner user found in database")
except Exception as e:
    print(f"Error: {str(e)}")

# Test 3: Admin user
print("\n" + "="*80)
print("TEST 3: Admin (authenticated)")
print("="*80)
try:
    admin_user = User.objects.filter(role='admin').first()
    if admin_user:
        result = get_assistant_reply("Quelles sont les validations en attente ?", user=admin_user)
        print(f"Response: {result['reply'][:200]}...")
        print(f"Source: {result['source']}")
        print(f"Matches: {len(result['matches'])}")
    else:
        print("No admin user found in database")
except Exception as e:
    print(f"Error: {str(e)}")

# Test 4: Client user
print("\n" + "="*80)
print("TEST 4: Client (authenticated)")
print("="*80)
try:
    client_user = User.objects.filter(role='client').first()
    if client_user:
        result = get_assistant_reply("Comment contacter un propriétaire ?", user=client_user)
        print(f"Response: {result['reply'][:200]}...")
        print(f"Source: {result['source']}")
        print(f"Matches: {len(result['matches'])}")
    else:
        print("No client user found in database")
except Exception as e:
    print(f"Error: {str(e)}")

# Test 5: Property search
print("\n" + "="*80)
print("TEST 5: Property Search (visitor)")
print("="*80)
result = get_assistant_reply("Je cherche une villa 3 chambres à Lomé", user=None)
print(f"Response: {result['reply'][:200]}...")
print(f"Source: {result['source']}")
print(f"Matches: {len(result['matches'])}")
if result['matches']:
    for match in result['matches']:
        print(f"  - {match.title}")

print("\n" + "="*80)
print("TEST COMPLETED")
print("="*80)
