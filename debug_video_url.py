"""
Debug video URL generation and accessibility
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from properties.models import Property

print("=== Debugging Video URLs ===\n")

# Get properties with videos
properties = Property.objects.filter(video_status='done', virtual_tour_video__isnull=False)

print(f"Properties with videos: {properties.count()}\n")

for prop in properties:
    print(f"Property: {prop.title} (ID: {prop.id})")
    print(f"Video status: {prop.video_status}")
    print(f"Video field: {prop.virtual_tour_video}")
    print(f"Video name: {prop.virtual_tour_video.name if prop.virtual_tour_video else 'None'}")
    print(f"Video URL: {prop.virtual_tour_video.url if prop.virtual_tour_video else 'None'}")
    
    # Check if file exists
    if prop.virtual_tour_video:
        from django.conf import settings
        import os
        full_path = os.path.join(settings.MEDIA_ROOT, prop.virtual_tour_video.name)
        print(f"Full path: {full_path}")
        print(f"File exists: {os.path.exists(full_path)}")
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print(f"File size: {size} bytes ({size/1024/1024:.2f} MB)")
    print()
