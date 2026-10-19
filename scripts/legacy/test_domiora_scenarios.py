"""
Test DOMIORA-specific scenarios for the AI assistant
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.ai_assistant import get_assistant_response

# DOMIORA-specific test scenarios
test_scenarios = [
    # Visitor scenarios
    ("visitor", "Bonjour, je cherche un appartement"),
    ("visitor", "Comment créer un compte ?"),
    ("visitor", "Comment contacter un propriétaire ?"),
    ("visitor", "Est-ce gratuit de consulter les annonces ?"),
    ("visitor", "Je veux visiter un bien, comment faire ?"),
    ("visitor", "Quel est le prix pour contacter un propriétaire ?"),
    
    # Owner scenarios
    ("owner", "Bonjour, je veux publier une maison"),
    ("owner", "Comment vérifier mon identité ?"),
    ("owner", "Est-ce payant de publier une annonce ?"),
    ("owner", "J'ai oublié mon mot de passe"),
    ("owner", "Comment ajouter une visite virtuelle ?"),
    
    # General DOMIORA questions
    ("visitor", "C'est quoi DOMIORA ?"),
    ("visitor", "Comment fonctionne la mise en relation ?"),
    ("visitor", "Qu'est-ce que CinetPay ?"),
    ("visitor", "Puis-je voir les vidéos des logements ?"),
    
    # Search scenarios
    ("visitor", "Je cherche une villa 3 chambres à Lomé"),
    ("visitor", "Appartement à louer à Paris"),
]

print("="*80)
print("TEST DOMIORA-SPECIFIC SCENARIOS")
print("="*80)

for role, message in test_scenarios:
    print(f"\n{'='*80}")
    print(f"Role: {role.upper()} | Message: {message}")
    print('='*80)
    
    try:
        result = get_assistant_response(message, user_role=role)
        print(f"\nResponse: {result['response'][:400]}...")
        
        if result['properties']:
            print(f"\nProperties found: {len(result['properties'])}")
            for prop in result['properties']:
                print(f"  - {prop['title']}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

print("\n" + "="*80)
print("TEST COMPLETED")
print("="*80)
