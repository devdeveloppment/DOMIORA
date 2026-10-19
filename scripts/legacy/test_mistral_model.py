"""Test direct du modèle Mistral configuré."""
import os
from mistralai.client import Mistral
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

api_key = settings.MISTRAL_API_KEY
model = settings.MISTRAL_MODEL

system_prompt = """
Tu es l'assistant IA intelligent de DOMIORA, une plateforme immobilière moderne.

Ton rôle est d'aider les utilisateurs de manière naturelle, comme un véritable conseiller immobilier.
"""

try:
    client = Mistral(api_key=api_key)
    response = client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Bonjour, comment tu vas ?"},
        ],
        temperature=0.7,
        max_tokens=500,
        timeout_ms=15000,
    )

    reply = response.choices[0].message.content
    print("SUCCESS!")
    print(f"Response: {reply}")
        
except Exception as e:
    print(f"Error: {str(e)}")
