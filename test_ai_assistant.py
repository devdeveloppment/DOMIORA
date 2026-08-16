"""
Test script for AI Assistant with intent detection
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.ai_assistant import detect_intent, get_assistant_response

# Test messages
test_messages = [
    ("Bonjour", "greeting"),
    ("Comment tu vas ?", "greeting"),
    ("Salut", "greeting"),
    ("Merci", "greeting"),
    ("Je cherche une villa 3 chambres à Lomé", "property_search"),
    ("Appartement à louer à Paris", "property_search"),
    ("Maison 4 chambres", "property_search"),
    ("C'est quoi DOMIORA ?", "domiora_question"),
    ("Comment ça marche ?", "domiora_question"),
    ("Comment créer un compte ?", "account_help"),
    ("Je veux m'inscrire", "account_help"),
    ("Comment publier une maison ?", "owner_help"),
    ("Vérification identité", "owner_help"),
    ("Quel est le prix moyen ?", "general_question"),
    ("Conseils pour acheter", "general_question"),
]

print("=" * 60)
print("TEST AI ASSISTANT - INTENT DETECTION")
print("=" * 60)

print("\n1. Testing intent detection:\n")
for message, expected_intent in test_messages:
    detected = detect_intent(message)
    status = "✓" if detected == expected_intent else "✗"
    print(f"{status} '{message}' -> {detected} (expected: {expected_intent})")

print("\n" + "=" * 60)
print("2. Testing full responses:\n")

# Test a few key scenarios
scenarios = [
    "Bonjour",
    "Comment tu vas ?",
    "C'est quoi DOMIORA ?",
    "Je cherche une villa à Lomé",
]

for message in scenarios:
    print(f"\nUser: {message}")
    result = get_assistant_response(message)
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['response'][:200]}...")
    if result['properties']:
        print(f"Properties found: {len(result['properties'])}")

print("\n" + "=" * 60)
print("TEST COMPLETED")
print("=" * 60)
