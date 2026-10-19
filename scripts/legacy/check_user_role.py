"""
Check current user roles to debug access issue
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("=== Checking User Roles ===\n")

# Get all users
users = User.objects.all()

for user in users:
    print(f"Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Role: {user.role}")
    print(f"  Is Superuser: {user.is_superuser}")
    print(f"  Is Active: {user.is_active}")
    print()

# Check specific users
print("=== Specific Users ===")
client_users = User.objects.filter(role='client')
print(f"Total clients: {client_users.count()}")
for u in client_users:
    print(f"  - {u.username} ({u.email})")

owner_users = User.objects.filter(role='owner')
print(f"Total owners: {owner_users.count()}")
for u in owner_users:
    print(f"  - {u.username} ({u.email})")

admin_users = User.objects.filter(role='admin')
print(f"Total admins: {admin_users.count()}")
for u in admin_users:
    print(f"  - {u.username} ({u.email})")
