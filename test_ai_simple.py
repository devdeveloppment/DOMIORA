"""
Test simple de l'IA DOMIORA sans emojis pour eviter les problemes d'encodage
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.ai_assistant import get_assistant_response

# Scenarios de test simples
test_scenarios = [
    ("Bonjour", "visitor"),
    ("Comment ca va ?", "visitor"),
    ("C'est quoi DOMIORA ?", "visitor"),
    ("Je cherche une villa 3 chambres a Lome", "visitor"),
    ("Comment contacter un proprietaire ?", "visitor"),
    ("Comment publier une annonce ?", "owner"),
    ("Comment verifier mon identite ?", "owner"),
    ("Comment payer les frais ?", "visitor"),
    ("C'est quoi la visite virtuelle ?", "visitor"),
    ("Merci pour ton aide", "visitor"),
]

print("="*80)
print("TEST SIMPLE DE L'IA DOMIORA")
print("="*80)

passed = 0
failed = 0
errors = []

for i, (message, role) in enumerate(test_scenarios, 1):
    print(f"\n{'='*80}")
    print(f"Test {i}/{len(test_scenarios)}: {message}")
    print(f"Role: {role}")
    print('='*80)
    
    try:
        result = get_assistant_response(message, user_role=role)
        response = result['response']
        properties = result.get('properties', [])
        
        print(f"\nReponse: {response[:200]}...")
        
        if properties:
            print(f"Proprietes trouvees: {len(properties)}")
        
        # Verifications basiques
        if len(response) < 10:
            print(f"WARNING: Reponse trop courte")
            failed += 1
            errors.append(f"Test {i}: Reponse trop courte")
        else:
            print(f"OK")
            passed += 1
            
    except Exception as e:
        print(f"ERREUR: {str(e)}")
        failed += 1
        errors.append(f"Test {i}: {str(e)}")

print(f"\n{'='*80}")
print("RESUME DU TEST")
print('='*80)
print(f"Reussis: {passed}/{len(test_scenarios)}")
print(f"Echoues: {failed}/{len(test_scenarios)}")
print(f"Taux de reussite: {passed/len(test_scenarios)*100:.1f}%")

if errors:
    print(f"\nErreurs detaillees:")
    for error in errors:
        print(f"   - {error}")
else:
    print(f"\nTous les tests sont passes avec succes!")
