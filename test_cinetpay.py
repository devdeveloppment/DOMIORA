"""
Script de diagnostic CinetPay - Lance depuis la racine du projet :
    python test_cinetpay.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import requests
import uuid
from django.conf import settings

print("=" * 60)
print("DIAGNOSTIC CINETPAY")
print("=" * 60)

api_key = getattr(settings, 'CINETPAY_API_KEY', '')
site_id = getattr(settings, 'CINETPAY_SITE_ID', '')

print(f"API Key   : {'OK (' + api_key[:8] + '...)' if api_key else '❌ VIDE'}")
print(f"Site ID   : {'OK (' + str(site_id) + ')' if site_id else '❌ VIDE'}")

if not api_key or not site_id:
    print("\n❌ ERREUR : Credentials CinetPay manquants dans .env")
    print("   Vérifiez CINETPAY_API_KEY et CINETPAY_SITE_ID dans votre .env")
    sys.exit(1)

transaction_id = "test-" + str(uuid.uuid4())[:8]

payload = {
    "apikey": api_key,
    "site_id": site_id,
    "transaction_id": transaction_id,
    "amount": 500,
    "currency": "XOF",
    "description": "Test diagnostic DOMIORA",
    "notify_url": "https://degrease-eaten-slightly.ngrok-free.dev/proprietes/test/payer/notify/",
    "return_url": "https://degrease-eaten-slightly.ngrok-free.dev/proprietes/test/payer/confirmation/",
    "channels": "ALL",
    "customer_name": "Test",
    "customer_surname": "Client",
    "customer_email": "test@domiora.com",
    "customer_phone_number": "22890000000",
    "customer_address": "Lome",
    "customer_city": "Lome",
    "customer_country": "TG",
    "customer_state": "TG",
    "customer_zip_code": "00000"
}

print(f"\nEnvoi requête à CinetPay (transaction: {transaction_id})...")

try:
    response = requests.post(
        "https://api-checkout.cinetpay.com/v2/payment",
        json=payload,
        timeout=15
    )
    print(f"\nHTTP Status : {response.status_code}")
    print(f"Réponse brute :\n{response.text}")
    
    data = response.json()
    code = str(data.get("code", ""))
    message = data.get("message", data.get("description", ""))
    
    print(f"\nCode retourné  : {code}")
    print(f"Message        : {message}")
    
    if code == "201":
        print(f"\n✅ SUCCÈS ! URL de paiement : {data['data']['payment_url']}")
    else:
        print(f"\n❌ ÉCHEC : Code={code} - {message}")
        if "data" in data:
            print(f"   Détails : {data['data']}")

except requests.exceptions.Timeout:
    print("❌ TIMEOUT : CinetPay ne répond pas dans les 15 secondes")
except requests.exceptions.RequestException as e:
    print(f"❌ ERREUR RÉSEAU : {e}")
except Exception as e:
    print(f"❌ ERREUR INATTENDUE : {e}")

print("\n" + "=" * 60)
