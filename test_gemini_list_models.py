"""
Lister les modèles Gemini disponibles avec cette clé API
"""
import requests
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

api_key = getattr(settings, 'GEMINI_API_KEY', '')
print(f"Listing available models for API key: {api_key[:20]}...")

# Lister les modèles disponibles
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n" + "="*60)
        print("AVAILABLE MODELS:")
        print("="*60)
        for model in data.get('models', []):
            name = model.get('name', 'Unknown')
            display_name = model.get('displayName', 'Unknown')
            print(f"\nName: {name}")
            print(f"Display: {display_name}")
            print(f"Supported methods: {model.get('supportedGenerationMethods', [])}")
except Exception as e:
    print(f"Error: {str(e)}")
