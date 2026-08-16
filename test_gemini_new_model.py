"""
Test avec le nouveau modèle gemini-2.5-flash
"""
import requests
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

api_key = getattr(settings, 'GEMINI_API_KEY', '')
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"

system_prompt = """
Tu es l'assistant IA intelligent de DOMIORA, une plateforme immobilière moderne.

Ton rôle est d'aider les utilisateurs de manière naturelle, comme un véritable conseiller immobilier.
"""

try:
    response = requests.post(
        f"{url}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": "Bonjour, comment tu vas ?"}]}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500,
            }
        },
        timeout=15,
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"✅ SUCCESS!")
        print(f"Response: {reply}")
    else:
        print(f"❌ Error: {response.text}")
        
except Exception as e:
    print(f"Error: {str(e)}")
