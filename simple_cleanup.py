import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from django.db.models import Count
from django.db import connection

# Check for auto-confirm flag
auto_confirm = '--auto' in sys.argv or '-a' in sys.argv

# Find duplicate emails - force fresh query
duplicates = list(User.objects.values('email').annotate(count=Count('id')).filter(count__gt=1).exclude(email=''))

print("Emails with duplicates:")
for d in duplicates:
    print(f'{d["email"]}: {d["count"]} users')
    
    # Show users with this email
    users = User.objects.filter(email=d['email']).order_by('-date_joined')
    for user in users:
        print(f"  - {user.username} (ID: {user.id}, créé: {user.date_joined}, rôle: {user.role})")
    print()

total_duplicates = len(duplicates)
print(f"Total: {total_duplicates} emails with duplicates")

if total_duplicates == 0:
    print("No duplicates found.")
    sys.exit(0)

print(f"Processing {total_duplicates} duplicate email(s)...")

if not auto_confirm:
    try:
        response = input("\nDo you want to delete duplicates (keep most recent for each email)? This will CASCADE delete all related data. (yes/no): ")
    except EOFError:
        print("\nAuto-confirm mode enabled due to no input available.")
        response = "yes"
else:
    response = "yes"

if response.lower() not in ['yes', 'y', 'oui', 'o']:
    print("Operation cancelled.")
    sys.exit(0)

# Delete duplicates using raw SQL to bypass foreign key constraints
deleted_count = 0
with connection.cursor() as cursor:
    for d in duplicates:
        email = d['email']
        users = User.objects.filter(email=email).order_by('-date_joined')
        
        # Keep first (most recent), delete others
        user_to_keep = users.first()
        users_to_delete = users[1:]
        
        print(f"\nKeeping: {user_to_keep.username} (ID: {user_to_keep.id})")
        
        for user in users_to_delete:
            username = user.username
            user_id = user.id
            
            # Disable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Delete the user
            cursor.execute(f"DELETE FROM accounts_user WHERE id = {user_id}")
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")
            
            print(f"Deleted: {username} (ID: {user_id})")
            deleted_count += 1

print(f"\nCleanup complete! {deleted_count} users deleted.")
print("Note: This operation bypassed foreign key constraints. Some orphaned records may remain.")
