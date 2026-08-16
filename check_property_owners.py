"""
Check which properties have owners and which don't
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from properties.models import Property, PropertyUnlock

print("=== Checking Property Owners ===\n")

# Get all properties
properties = Property.objects.all()
print(f"Total properties: {properties.count()}\n")

# Check which have owners
with_owner = properties.filter(owner__isnull=False)
without_owner = properties.filter(owner__isnull=True)

print(f"Properties with owner: {with_owner.count()}")
print(f"Properties without owner: {without_owner.count()}\n")

# Show properties without owner
if without_owner.exists():
    print("Properties WITHOUT owner:")
    for p in without_owner:
        print(f"  - {p.title} (ID: {p.id})")

# Show properties with owner
if with_owner.exists():
    print("\nProperties WITH owner:")
    for p in with_owner:
        print(f"  - {p.title} (ID: {p.id}, Owner: {p.owner.username})")

# Check property unlocks
unlocks = PropertyUnlock.objects.all()
print(f"\n=== Property Unlocks ===")
print(f"Total unlocks: {unlocks.count()}\n")

for unlock in unlocks:
    try:
        property_obj = Property.objects.get(id=unlock.property_id) if unlock.property_id else None
    except Property.DoesNotExist:
        property_obj = None
    
    if property_obj:
        has_owner = property_obj.owner is not None
        print(f"User: {unlock.user.username}")
        print(f"  Property: {property_obj.title}")
        print(f"  Has owner: {has_owner}")
        if has_owner:
            print(f"  Owner: {property_obj.owner.username}")
        print()
