"""
Test video generation directly without Celery
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from properties.models import Property
from properties.tasks import generate_virtual_tour_task

print("=== Testing Video Generation ===\n")

# Get a property with at least 2 images
properties = Property.objects.all()
print(f"Total properties: {properties.count()}")

for prop in properties:
    img_count = prop.images.count()
    print(f"Property: {prop.title} - Images: {img_count} - Video status: {prop.video_status}")
    
    if img_count >= 2:
        print(f"\n--- Testing video generation for: {prop.title} ---")
        result = generate_virtual_tour_task(prop.id)
        print(f"Result: {result}")
        
        # Check updated status
        prop.refresh_from_db()
        print(f"New video status: {prop.video_status}")
        if prop.virtual_tour_video:
            print(f"Video path: {prop.virtual_tour_video.name}")
        break
else:
    print("❌ No property with at least 2 images found")
