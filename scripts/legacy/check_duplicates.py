import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from django.db.models import Count

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
