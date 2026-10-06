import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from properties.models import PropertyImage

for img in PropertyImage.objects.all():
    name = img.image.name
    if not name.startswith("properties/") and name.endswith(".webp"):
        # The physical file is in properties/2026/08/... we have to find it.
        # Actually, let's just find where it exists
        possible_path = f"properties/2026/08/{name}"
        if os.path.exists(os.path.join(django.conf.settings.MEDIA_ROOT, possible_path)):
            print(f"Fixing {name} -> {possible_path}")
            PropertyImage.objects.filter(pk=img.pk).update(image=possible_path)
        else:
            print(f"Could not find physical file for {name}")

print("Done")
