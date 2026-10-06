from mistralai.client import Mistral
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings

API_KEY = settings.MISTRAL_API_KEY
MODEL = settings.MISTRAL_MODEL

print("=== Testing Mistral API ===")
print(f"API Key configured: {bool(API_KEY)}")
print(f"Model: {MODEL}")

if not API_KEY:
    raise SystemExit("MISTRAL_API_KEY is not configured")

try:
    client = Mistral(api_key=API_KEY)
    response = client.chat.complete(
        model=MODEL,
        messages=[{"role": "user", "content": "Bonjour, réponds simplement 'OK'"}],
        temperature=0.7,
        max_tokens=50,
        timeout_ms=15000,
    )

    reply = response.choices[0].message.content.strip()
    print(f"\nSuccess! Reply: {reply}")
        
except Exception as e:
    print(f"\nException: {e}")
    print(f"Error type: {type(e).__name__}")
