import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from django.db.models import Count

# Check all users
total_users = User.objects.count()
print(f"Total users in database: {total_users}")

# Check for empty emails
empty_emails = User.objects.filter(email='').count()
print(f"Users with empty email: {empty_emails}")

# Check for duplicate emails
duplicates = User.objects.values('email').annotate(count=Count('id')).filter(count__gt=1).exclude(email='')
print(f"Emails with duplicates: {duplicates.count()}")

# Show sample users
print("\nSample users:")
for user in User.objects.all()[:5]:
    print(f"  - {user.username} ({user.email}) - {user.role}")
