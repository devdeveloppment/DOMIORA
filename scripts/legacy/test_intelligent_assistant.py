"""
Test the new intelligent AI assistant
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.ai_assistant import get_assistant_response

# Test messages covering different scenarios
test_scenarios = [
    "Bonjour",
    "Comment tu vas ?",
    "Qui es-tu ?",
    "C'est quoi DOMIORA ?",
    "Je cherche une villa 3 chambres à Lomé",
    "Comment créer un compte ?",
    "Comment publier une propriété ?",
    "J'ai oublié mon mot de passe",
    "Quel est le prix moyen à Lomé ?",
    "Merci pour ton aide",
]

print("="*70)
print("TEST INTELLIGENT AI ASSISTANT - DOMIORA")
print("="*70)

for i, message in enumerate(test_scenarios, 1):
    print(f"\n{'='*70}")
    print(f"Test {i}: {message}")
    print('='*70)
    
    try:
        result = get_assistant_response(message)
        print(f"\nResponse: {result['response'][:300]}...")
        
        if result['properties']:
            print(f"\nProperties found: {len(result['properties'])}")
            for prop in result['properties']:
                print(f"  - {prop['title']}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

print("\n" + "="*70)
print("TEST COMPLETED")
print("="*70)
