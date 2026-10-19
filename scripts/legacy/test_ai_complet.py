"""
Test complet de l'IA DOMIORA avec des scenarios realistes
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.ai_assistant import get_assistant_response

# Scenarios de test plus realistes et varies
test_scenarios = [
    # Scenarios visiteurs - recherche
    ("Je cherche un appartement 2 chambres a Lome avec un budget de 500000 FCFA", "visitor"),
    ("Je veux une villa a Lome pas trop chere", "visitor"),
    ("Studio a louer dans le centre de Lome", "visitor"),
    
    # Scenarios visiteurs - questions processus
    ("Est-ce que je dois m'inscrire pour voir les annonces ?", "visitor"),
    ("Comment faire pour voir le telephone du proprietaire ?", "visitor"),
    ("C'est quoi les frais de mise en relation ?", "visitor"),
    ("Je peux payer avec Orange Money ?", "visitor"),
    
    # Scenarios visiteurs - fonctionnalites
    ("Les photos sont gratuites a voir ?", "visitor"),
    ("Comment fonctionne la visite virtuelle ?", "visitor"),
    ("Je peux faire une visite sans payer ?", "visitor"),
    
    # Scenarios proprietaires - publication
    ("Je veux mettre mon appartement en location sur DOMIORA", "owner"),
    ("Combien ca coute de publier une annonce ?", "owner"),
    ("Quels documents il faut pour verifier mon identite ?", "owner"),
    ("Combien de temps pour que mon annonce soit en ligne ?", "owner"),
    
    # Scenarios proprietaires - gestion
    ("Comment modifier mon annonce ?", "owner"),
    ("Je peux supprimer mon annonce ?", "owner"),
    ("Comment ajouter des photos a mon annonce ?", "owner"),
    
    # Scenarios admin
    ("J'ai une nouvelle demande de validation de proprietaire", "admin"),
    ("Comment verifier les documents d'identite ?", "admin"),
    ("Que faire si un proprietaire a des faux documents ?", "admin"),
    
    # Scenarios support
    ("J'ai paye mais je n'ai pas acces au proprietaire", "visitor"),
    ("Le proprietaire ne repond pas a mes messages", "visitor"),
    ("Je veux changer mon mot de passe", "visitor"),
    ("Comment signaler une annonce frauduleuse ?", "visitor"),
    
    # Scenarios divers
    ("DOMIORA est disponible dans d'autres pays ?", "visitor"),
    ("Puis-je trouver des terrains a vendre ?", "visitor"),
    ("Comment fonctionne la securite des paiements ?", "visitor"),
]

print("="*80)
print("TEST COMPLET DE L'IA DOMIORA - SCENARIOS REALISTES")
print("="*80)

passed = 0
failed = 0
errors = []
responses_details = []

for i, (message, role) in enumerate(test_scenarios, 1):
    print(f"\n{'='*80}")
    print(f"Test {i}/{len(test_scenarios)}: {message}")
    print(f"Role: {role}")
    print('='*80)
    
    try:
        result = get_assistant_response(message, user_role=role)
        response = result['response']
        properties = result.get('properties', [])
        
        print(f"\nReponse: {response[:150]}...")
        
        if properties:
            print(f"Proprietes trouvees: {len(properties)}")
        
        # Sauvegarder les details pour analyse
        responses_details.append({
            'test': i,
            'message': message,
            'role': role,
            'response': response[:200],
            'has_properties': len(properties) > 0
        })
        
        # Verifications basiques
        if len(response) < 15:
            print(f"WARNING: Reponse trop courte")
            failed += 1
            errors.append(f"Test {i}: Reponse trop courte")
        elif "erreur" in response.lower() or "error" in response.lower():
            print(f"WARNING: Reponse contient une erreur")
            failed += 1
            errors.append(f"Test {i}: Reponse contient une erreur")
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

# Analyse de la qualite des reponses
print(f"\n{'='*80}")
print("ANALYSE DE LA QUALITE DES REPONSES")
print('='*80)

visitor_tests = [r for r in responses_details if r['role'] == 'visitor']
owner_tests = [r for r in responses_details if r['role'] == 'owner']
admin_tests = [r for r in responses_details if r['role'] == 'admin']

print(f"\nTests visiteurs: {len(visitor_tests)}")
print(f"Tests proprietaires: {len(owner_tests)}")
print(f"Tests admin: {len(admin_tests)}")

# Verifier si les reponses sont specifiques et non generiques
generic_responses = [r for r in responses_details if "DOMIORA" in r['response'] and len(r['response']) < 100]
print(f"\nReponses potentiellement trop generiques: {len(generic_responses)}")

if generic_responses:
    print("Tests avec reponses generiques:")
    for r in generic_responses:
        print(f"   - Test {r['test']}: {r['message']}")
