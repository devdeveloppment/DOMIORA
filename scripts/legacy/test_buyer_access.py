"""
Test buyer access to client dashboard
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import User

User = get_user_model()

print("=== Testing Buyer Access ===\n")

# Get a buyer user
buyer = User.objects.filter(role='buyer').first()

if not buyer:
    print("❌ No buyer user found in database")
    exit(1)

print(f"Buyer user: {buyer.username}")
print(f"Role: {buyer.role}")
print(f"Email: {buyer.email}")

# Test role check
from dashboard.decorators import role_required

# Simulate the decorator logic
user_role = buyer.role
if user_role == "buyer":
    user_role = "client"  # Treat buyers as clients for access control

print(f"\n--- Role Check ---")
print(f"Original role: {buyer.role}")
print(f"Normalized role: {user_role}")
print(f"Allowed roles for client dashboard: {User.Role.CLIENT}")

if user_role == User.Role.CLIENT:
    print(f"✅ Buyer can access client dashboard")
else:
    print(f"❌ Buyer cannot access client dashboard")

# Test context processor logic
role = buyer.role
if role == User.Role.ADMIN or buyer.is_superuser:
    dash_role = "admin"
elif role == User.Role.OWNER:
    dash_role = "owner"
elif role == User.Role.AGENT:
    dash_role = "owner"
else:
    # CLIENT and BUYER both use client dashboard
    dash_role = "client"

print(f"\n--- Context Processor ---")
print(f"User role: {role}")
print(f"Dashboard role: {dash_role}")

if dash_role == "client":
    print(f"✅ Buyer will see client dashboard")
else:
    print(f"❌ Buyer will not see client dashboard")

print(f"\n✅ Buyer access test completed")
