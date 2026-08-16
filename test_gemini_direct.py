"""
Test direct de l'API Gemini pour déboguer l'erreur 404
"""
import requests
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

api_key = getattr(settings, 'GEMINI_API_KEY', '')
print(f"API Key length: {len(api_key)}")
print(f"API Key starts with: {api_key[:20] if api_key else 'None'}...")

# Test avec différentes URLs
urls_to_test = [
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
    "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
]

for url in urls_to_test:
    print(f"\n{'='*60}")
    print(f"Testing URL: {url}")
    print('='*60)
    
    try:
        response = requests.post(
            f"{url}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": "Bonjour"}]}
                ]
            },
            timeout=10,
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✅ SUCCESS! This URL works.")
            break
    except Exception as e:
        print(f"Error: {str(e)}")

print("\n" + "="*60)
print("Test completed")
