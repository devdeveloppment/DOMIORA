"""
Test de l'integration de l'IA avec le systeme de vues Django
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.ai_assistant import get_assistant_reply
from django.contrib.auth import get_user_model

User = get_user_model()

print("="*80)
print("TEST D'INTEGRATION IA DOMIORA - VIEWS DJANGO")
print("="*80)

# Test avec utilisateur non authentifie (visiteur)
print("\n1. Test avec visiteur (non authentifie):")
result = get_assistant_reply("Je cherche un appartement a Lome", user=None)
print(f"Reponse: {result['reply'][:100]}...")
print(f"Matches: {len(result['matches'])}")
print(f"Source: {result['source']}")

# Test avec proprietaire
print("\n2. Test avec proprietaire:")
try:
    owner = User.objects.filter(role='owner').first()
    if owner:
        result = get_assistant_reply("Comment publier une annonce ?", user=owner)
        print(f"Reponse: {result['reply'][:100]}...")
        print(f"Matches: {len(result['matches'])}")
        print(f"Source: {result['source']}")
    else:
        print("Aucun proprietaire trouve dans la base")
except Exception as e:
    print(f"Erreur: {e}")

# Test avec admin
print("\n3. Test avec admin:")
try:
    admin = User.objects.filter(role='admin').first()
    if admin:
        result = get_assistant_reply("Comment valider un proprietaire ?", user=admin)
        print(f"Reponse: {result['reply'][:100]}...")
        print(f"Matches: {len(result['matches'])}")
        print(f"Source: {result['source']}")
    else:
        print("Aucun admin trouve dans la base")
except Exception as e:
    print(f"Erreur: {e}")

# Test avec historique de conversation
print("\n4. Test avec historique de conversation:")
history = [
    {'role': 'user', 'content': 'Bonjour'},
    {'role': 'assistant', 'content': 'Bonjour ! Je suis l assistant DOMIORA.'},
    {'role': 'user', 'content': 'Je cherche une villa'}
]
result = get_assistant_reply("A Lome avec 3 chambres", conversation_history=history, user=None)
print(f"Reponse: {result['reply'][:100]}...")
print(f"Matches: {len(result['matches'])}")
print(f"Source: {result['source']}")

print("\n" + "="*80)
print("TEST D'INTEGRATION TERMINE")
print("="*80)
