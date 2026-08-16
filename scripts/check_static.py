import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.staticfiles.finders import find

path = find('images/hero-illustration.svg')
print('found:', path)
