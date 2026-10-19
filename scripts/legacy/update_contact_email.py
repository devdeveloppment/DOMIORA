import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from site_settings.models import SiteSettings

s = SiteSettings.load()
if s:
    s.contact_email = 'denistchil@gmail.com'
    s.save()
    print("Mise à jour réussie : l'email de contact du site est maintenant denistchil@gmail.com")
