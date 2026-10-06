"""
Test direct de l'endpoint API de l'assistant
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
import json

from core.views import assistant_chat

User = get_user_model()

print("="*80)
print("TEST DIRECT DE L'ENDPOINT API ASSISTANT")
print("="*80)

# Creer une factory de requetes
factory = RequestFactory()

# Test avec utilisateur admin
try:
    admin = User.objects.filter(role='admin').first()
    if admin:
        print(f"\n1. Test avec admin: {admin.username}")
        
        # Simuler une requete POST
        payload = {
            "message": "salut",
            "history": []
        }
        
        request = factory.post(
            '/api/assistant/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        request.user = admin
        
        # Appeler la vue
        response = assistant_chat(request)
        
        print(f"Status code: {response.status_code}")
        print(f"Response content: {response.content.decode('utf-8')}")
        
        # Parser la reponse JSON
        response_data = json.loads(response.content.decode('utf-8'))
        print(f"Reply: {response_data.get('reply', 'NO REPLY')[:100]}...")
        print(f"Matches: {len(response_data.get('matches', []))}")
        print(f"Source: {response_data.get('source', 'NO SOURCE')}")
        
    else:
        print("Aucun admin trouve")
        
except Exception as e:
    print(f"Erreur: {e}")
    import traceback
    traceback.print_exc()

# Test avec visiteur (non authentifie)
print(f"\n2. Test avec visiteur (non authentifie):")
try:
    payload = {
        "message": "salut",
        "history": []
    }
    
    request = factory.post(
        '/api/assistant/',
        data=json.dumps(payload),
        content_type='application/json'
    )
    request.user = type('AnonymousUser', (), {'is_authenticated': False})()
    
    response = assistant_chat(request)
    
    print(f"Status code: {response.status_code}")
    print(f"Response content: {response.content.decode('utf-8')}")
    
    response_data = json.loads(response.content.decode('utf-8'))
    print(f"Reply: {response_data.get('reply', 'NO REPLY')[:100]}...")
    print(f"Matches: {len(response_data.get('matches', []))}")
    print(f"Source: {response_data.get('source', 'NO SOURCE')}")
    
except Exception as e:
    print(f"Erreur: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("TEST TERMINE")
print("="*80)
