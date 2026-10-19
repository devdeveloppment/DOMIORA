import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from django.db.models import Count
from django.db import transaction

# Check for auto-confirm flag
auto_confirm = '--auto' in sys.argv or '-a' in sys.argv

# Find duplicate emails
duplicates = User.objects.values('email').annotate(count=Count('id')).filter(count__gt=1).exclude(email='')

print("Emails with duplicates:")
for d in duplicates:
    print(f'{d["email"]}: {d["count"]} users')
    
    # Show users with this email
    users = User.objects.filter(email=d['email']).order_by('-date_joined')
    for user in users:
        print(f"  - {user.username} (ID: {user.id}, créé: {user.date_joined}, rôle: {user.role})")
    print()

total_duplicates = duplicates.count()
print(f"Total: {total_duplicates} emails with duplicates")

if total_duplicates == 0:
    print("No duplicates found.")
    sys.exit(0)

if not auto_confirm:
    try:
        response = input("\nDo you want to delete duplicates (keep most recent for each email)? (yes/no): ")
    except EOFError:
        print("\nAuto-confirm mode enabled due to no input available.")
        response = "yes"
else:
    response = "yes"

if response.lower() not in ['yes', 'y', 'oui', 'o']:
    print("Operation cancelled.")
    sys.exit(0)

# Delete duplicates
deleted_count = 0
with transaction.atomic():
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
            
            # First, handle foreign key constraints by setting to NULL or transferring
            try:
                # Check for properties owned by this user
                if hasattr(user, 'properties'):
                    props = user.properties.all()
                    if props.exists():
                        print(f"  -> Transferring {props.count()} properties to {user_to_keep.username}")
                        props.update(owner=user_to_keep)
                
                # Check for conversations as buyer
                if hasattr(user, 'conversations_as_buyer'):
                    convs = user.conversations_as_buyer.all()
                    if convs.exists():
                        from messaging.models import Conversation
                        for conv in convs:
                            # Check if duplicate conversation would exist
                            existing = Conversation.objects.filter(
                                buyer=user_to_keep,
                                owner=conv.owner,
                                property=conv.property
                            ).first()
                            if existing:
                                # Transfer messages to existing conversation
                                conv.messages.update(conversation=existing)
                                conv.delete()
                            else:
                                conv.buyer = user_to_keep
                                conv.save()
                        print(f"  -> Transferred/merged conversations")
                
                # Check for messages sent
                if hasattr(user, 'sent_messages'):
                    msgs = user.sent_messages.all()
                    if msgs.exists():
                        msgs.update(sender=user_to_keep)
                        print(f"  -> Transferred {msgs.count()} messages")
                
                # Now delete the user
                user.delete()
                print(f"Deleted: {username} (ID: {user_id})")
                deleted_count += 1
                
            except Exception as e:
                print(f"Error deleting {username}: {e}")
                raise

print(f"\nCleanup complete! {deleted_count} users deleted.")
