"""
Test de l'IA DOMIORA actuelle avec scénarios complets
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.ai_assistant import get_assistant_response

# Scénarios de test complets couvrant tous les aspects
test_scenarios = [
    # Salutations et base
    ("Bonjour", "visitor"),
    ("Comment ça va ?", "visitor"),
    ("Qui es-tu ?", "visitor"),
    
    # Questions générales sur DOMIORA
    ("C'est quoi DOMIORA ?", "visitor"),
    ("Comment ça marche ?", "visitor"),
    ("Comment fonctionne DOMIORA ?", "visitor"),
    
    # Recherche de biens
    ("Je cherche une villa 3 chambres à Lomé", "visitor"),
    ("Appartement à louer à Paris", "visitor"),
    ("Maison 4 chambres pas cher", "visitor"),
    ("Studio à Lomé", "visitor"),
    
    # Processus client (visiteur)
    ("Comment contacter un propriétaire ?", "visitor"),
    ("Comment créer un compte ?", "visitor"),
    ("Est-ce que je dois m'inscrire ?", "visitor"),
    ("Comment voir les coordonnées du propriétaire ?", "visitor"),
    ("Quels sont les frais pour contacter ?", "visitor"),
    
    # Processus propriétaire
    ("Comment publier une annonce ?", "owner"),
    ("Est-ce gratuit de publier ?", "owner"),
    ("Comment vérifier mon identité ?", "owner"),
    ("Quels documents pour la vérification ?", "owner"),
    ("Combien de temps pour la validation ?", "owner"),
    
    # Paiement et CinetPay
    ("Comment payer les frais de mise en relation ?", "visitor"),
    ("C'est quoi CinetPay ?", "visitor"),
    ("Est-ce sécurisé le paiement ?", "visitor"),
    
    # Fonctionnalités avancées
    ("C'est quoi la visite virtuelle ?", "visitor"),
    ("Comment faire une visite ?", "visitor"),
    ("Puis-je voir les photos avant de payer ?", "visitor"),
    
    # Admin
    ("Comment valider un propriétaire ?", "admin"),
    ("Que faire quand il y a une nouvelle inscription ?", "admin"),
    
    # Problèmes et support
    ("J'ai oublié mon mot de passe", "visitor"),
    ("Le propriétaire ne répond pas", "visitor"),
    ("Comment signaler un problème ?", "visitor"),
    
    # Remerciements
    ("Merci pour ton aide", "visitor"),
    ("Au revoir", "visitor"),
]

print("="*80)
print("TEST COMPLET DE L IA DOMIORA")
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
        
        print(f"\nReponse: {response[:300]}...")
        
        if properties:
            print(f"Proprietes trouvees: {len(properties)}")
            for prop in properties[:2]:
                print(f"   - {prop['title']}")
        
        # Vérifications basiques
        if len(response) < 20:
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
