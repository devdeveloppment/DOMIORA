"""
AI Assistant Service for DOMIORA
Intelligent context-aware assistant using Gemini API
"""
import os
import requests
import re
import logging
from django.conf import settings
from properties.models import Property

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"

# Sophisticated system prompt for intelligent assistant with complete DOMIORA business context
SYSTEM_PROMPT = """
Tu es l'assistant IA intelligent de DOMIORA, une plateforme immobilière intelligente SaaS.

## CONTEXTE COMPLET DOMIORA

### 1. Présentation générale

DOMIORA est une plateforme immobilière intelligente permettant de connecter directement :
- Les propriétaires qui souhaitent publier leurs biens
- Les clients/visiteurs qui recherchent un logement
- L'administrateur principal qui supervise toute la plateforme

### 2. Les trois rôles principaux

#### A. Administrateur principal
L'administrateur est le responsable global de DOMIORA. Il supervise :
- Les propriétaires inscrits
- Les validations d'identité
- Les annonces publiées
- Les paiements
- Les demandes de mise en relation
- Les activités de la plateforme

**Validation des propriétaires** :
- Le propriétaire fournit ses informations et une pièce d'identité (CNI, passeport, etc.)
- L'administrateur vérifie les informations
- Il accepte ou refuse le profil
- Tant que non validé, le propriétaire ne peut pas publier de biens
- Après validation, son compte devient actif et il peut publier gratuitement ses annonces

#### B. Propriétaire
Le propriétaire est le seul utilisateur qui doit obligatoirement :
- Créer un compte
- Se connecter
- Compléter son profil
- Faire vérifier son identité

Après validation, il peut :
- Publier gratuitement ses annonces (titre, description, type, localisation, prix, pièces, équipements, photos)
- Ajouter une visite virtuelle (images + vidéo)
- Recevoir des demandes de visiteurs
- Échanger avec les clients ayant débloqué ses informations
- Organiser des visites

#### C. Client / Visiteur
Le client n'a PAS besoin de créer un compte. Il peut directement :
- Consulter les annonces
- Rechercher des biens
- Utiliser les filtres
- Voir les photos et vidéos de visite virtuelle
- Consulter les descriptions complètes

**Consultation d'un bien** :
- Le client voit description, photos, vidéo, caractéristiques, localisation
- Les informations privées du propriétaire restent masquées

### 3. Processus de mise en relation

Lorsqu'un client est intéressé :
1. Il clique sur "Demander une visite" ou "Prendre rendez-vous"
2. Le système indique : "Pour accéder aux coordonnées du propriétaire et débloquer la mise en relation, vous devez payer les frais de mise en relation."
3. Montant : 500 FCFA
4. Paiement via CinetPay
5. Après confirmation : création espace client temporaire + accès informations propriétaire

### 4. Dashboard client après paiement
Après paiement réussi, le client obtient un espace léger permettant :
- Accéder aux coordonnées du propriétaire
- Envoyer des messages
- Échanger avec le propriétaire
- Gérer ses demandes de visites

### 5. Règles critiques pour l'IA

❌ JAMAIS dire : "Créez un compte client pour contacter un propriétaire"
✅ TOUJOURS dire : "Vous pouvez consulter les biens librement. Lorsque vous souhaitez contacter un propriétaire ou demander une visite, il suffit de débloquer la mise en relation (500 FCFA via CinetPay)."

### 6. Fonctionnalités clés
- Publication gratuite pour propriétaires validés
- Visite virtuelle intégrée (images + vidéo)
- Frais de mise en relation : 500 FCFA
- Paiement via CinetPay
- Espace client temporaire après paiement
- Vérification d'identité obligatoire pour propriétaires

### 7. Ton rôle

Tu dois comprendre cette logique métier spécifique à DOMIORA et ne jamais utiliser un fonctionnement classique d'agence immobilière ou de site d'annonces traditionnel.

Avant de répondre à une demande utilisateur :
- Identifie son rôle (client visiteur, propriétaire ou administrateur)
- Comprends l'étape actuelle de son parcours
- Adapte ta réponse aux fonctionnalités réellement disponibles dans DOMIORA

**IMPORTANT** : Ne mentionne JAMAIS le rôle de l'utilisateur dans tes réponses. Ne dis pas "Bonjour cher administrateur", "En tant que propriétaire", etc. Réponds simplement en tant qu'assistant DOMIORA en adaptant le contenu selon le rôle, mais sans le mentionner explicitement.

### 8. Actions possibles

**Pour un visiteur** :
- Expliquer comment fonctionne DOMIORA
- Rechercher des biens
- Expliquer les annonces et la visite virtuelle
- Expliquer les frais de mise en relation (500 FCFA)
- Guider vers le paiement CinetPay

**Pour un propriétaire** :
- Expliquer l'inscription
- Expliquer la vérification d'identité (obligatoire)
- Expliquer la publication d'annonce (gratuite après validation)
- Aider à comprendre les étapes

**Pour l'administrateur** :
- Notifier les nouvelles demandes
- Signaler les validations nécessaires
- Suivre les événements importants

### 9. Style de communication
- Professionnel mais chaleureux
- Langage simple et compréhensible
- Adapte ton niveau d'explication à l'utilisateur
- Agis comme un conseiller immobilier disponible 24h/24

### 10. Limites
- Ne prétends jamais avoir effectué une action que tu n'as pas faite
- Ne crée jamais de faux logements, prix ou informations
- Utilise uniquement les données disponibles dans les outils connectés
- Respecte toujours la logique métier DOMIORA

### Objectif principal
Créer une expérience où l'utilisateur a l'impression de discuter avec un véritable expert immobilier connaissant parfaitement DOMIORA, capable de comprendre toutes ses demandes et de le guider selon le fonctionnement réel de la plateforme.
"""


def extract_search_criteria(message):
    """
    Extract property search criteria from message using Gemini
    Returns: dict with criteria (city, bedrooms, budget, etc.) or None
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return None
    
    prompt = f"""
    Analyse ce message utilisateur et extrais les critères de recherche immobilière s'ils sont présents.
    Message: "{message}"
    
    Si le message ne concerne PAS une recherche de logement, retourne "NO_SEARCH".
    
    Si c'est une recherche, retourne un JSON avec ces champs (null si non spécifié):
    {{
        "city": "ville ou null",
        "bedrooms": nombre ou null,
        "budget": "montant ou null",
        "property_type": "apartment/house/studio ou null",
        "transaction_type": "rent/sale ou null"
    }}
    
    Retourne UNIQUEMENT le JSON, sans autre texte.
    """
    
    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 200,
                }
            },
            timeout=10,
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            result = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            if "NO_SEARCH" in result:
                return None
            
            # Parse JSON
            import json
            try:
                criteria = json.loads(result)
                return criteria
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse criteria JSON: {result}")
                return None
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting search criteria: {str(e)}")
        return None


def search_properties_with_criteria(criteria):
    """
    Search properties based on extracted criteria
    Returns: QuerySet of Property objects
    """
    queryset = Property.objects.filter(is_published=True, status='available')
    
    if criteria.get('city'):
        queryset = queryset.filter(city__icontains=criteria['city'])
    
    if criteria.get('bedrooms'):
        queryset = queryset.filter(bedrooms=criteria['bedrooms'])
    
    if criteria.get('property_type'):
        queryset = queryset.filter(property_type=criteria['property_type'])
    
    if criteria.get('transaction_type'):
        queryset = queryset.filter(transaction_type=criteria['transaction_type'])
    
    return queryset[:5]  # Limit to 5 results


def generate_intelligent_response(message, properties=None, conversation_history=None, user_role=None):
    """
    Generate intelligent response using Gemini with context awareness and role
    
    Args:
        message: User message
        properties: QuerySet of properties (if search was performed)
        conversation_history: List of previous messages for context
        user_role: User role - 'visitor', 'owner', or 'admin'
    
    Returns: str - Natural intelligent response
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return _generate_fallback_response(message, properties, user_role)
    
    # Build context
    context = ""
    if properties and properties.exists():
        property_list = []
        for prop in properties:
            property_list.append(
                f"- {prop.title} | {prop.get_property_type_display()} | {prop.price_display} | "
                f"{prop.city}, {prop.country} | {prop.bedrooms} ch. / {prop.bathrooms} sdb. / {prop.surface_area} m²"
            )
        context = f"\n\nLogements disponibles correspondant à la recherche:\n" + "\n".join(property_list)
    
    # Build conversation context
    conversation_context = ""
    if conversation_history and len(conversation_history) > 0:
        recent_history = conversation_history[-5:]  # Last 5 messages
        conversation_context = "\n\nHistorique de conversation récent:\n"
        for msg in recent_history:
            role = "Utilisateur" if msg.get('role') == 'user' else "Assistant"
            conversation_context += f"{role}: {msg.get('content', '')}\n"
    
    # Build role context
    role_context = ""
    if user_role:
        role_mapping = {
            'visitor': 'Client / Visiteur',
            'owner': 'Propriétaire',
            'admin': 'Administrateur'
        }
        role_context = f"\n\nRôle de l'utilisateur: {role_mapping.get(user_role, user_role)}"
    
    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "contents": [
                    {"role": "user", "parts": [{"text": f"{context}{conversation_context}{role_context}\n\nMessage actuel: {message}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 800,
                }
            },
            timeout=20,
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return reply
        
        return _generate_fallback_response(message, properties, user_role)
        
    except Exception as e:
        logger.error(f"Gemini response generation error: {str(e)}")
        return _generate_fallback_response(message, properties, user_role)


def get_assistant_response(message, conversation_history=None, user_role=None):
    """
    Main entry point for the intelligent assistant
    
    Args:
        message: User message
        conversation_history: List of previous messages (optional)
        user_role: User role - 'visitor', 'owner', or 'admin' (optional)
    
    Returns:
        dict: {
            'response': str,
            'properties': list (if search was performed)
        }
    """
    logger.info(f"Processing message: {message[:100]}... (Role: {user_role or 'unknown'})")
    
    # Step 1: Extract search criteria using Gemini
    criteria = extract_search_criteria(message)
    
    # Step 2: Search properties if criteria found
    properties = None
    if criteria:
        logger.info(f"Search criteria extracted: {criteria}")
        properties = search_properties_with_criteria(criteria)
    
    # Step 3: Generate intelligent response with context and role
    response = generate_intelligent_response(message, properties, conversation_history, user_role)
    
    # Step 4: Format properties for response
    properties_data = []
    if properties and properties.exists():
        for prop in properties:
            properties_data.append({
                'id': prop.id,  # Add ID for Property object reconstruction
                'title': prop.title,
                'url': prop.get_absolute_url(),
                'price': prop.price_display,
                'image': prop.primary_image,
                'city': prop.city,
                'country': prop.country,
                'bedrooms': prop.bedrooms,
                'surface_area': prop.surface_area
            })
    
    return {
        'response': response,
        'properties': properties_data
    }


def _generate_fallback_response(message, properties=None, user_role=None):
    """Fallback responses when Gemini is unavailable with role awareness"""
    message_lower = message.lower()
    
    # Check for greetings
    greetings = ['bonjour', 'salut', 'hello', 'hi', 'coucou', 'bonsoir', 'bienvenue', 'hey']
    if any(g in message_lower for g in greetings):
        return "Bonjour 👋 Je suis l'assistant DOMIORA. Comment puis-je vous aider aujourd'hui ?"
    
    # Check for how are you
    how_are_you = ['comment ça va', 'comment vas-tu', 'ça va', 'tu vas', 'comment allez-vous']
    if any(h in message_lower for h in how_are_you):
        return "Je vais très bien merci 😊. Je suis l'assistant DOMIORA et je suis là pour vous aider à trouver un logement ou répondre à vos questions. Et vous, comment allez-vous ?"
    
    # Check for thanks
    thanks = ['merci', 'thanks', 'thank you']
    if any(t in message_lower for t in thanks):
        return "Je vous en prie ! N'hésitez pas si vous avez d'autres questions. 😊"
    
    # Role-specific responses
    if user_role == 'visitor':
        if 'compte' in message_lower and ('créer' in message_lower or 'inscription' in message_lower):
            return "Sur DOMIORA, vous n'avez pas besoin de créer un compte pour consulter les biens. Vous pouvez parcourir toutes les annonces librement. Lorsque vous souhaitez contacter un propriétaire ou demander une visite, il suffit de débloquer la mise en relation (500 FCFA via CinetPay). 🏠"
        elif 'contacter' in message_lower or 'propriétaire' in message_lower:
            return "Pour contacter un propriétaire sur DOMIORA, vous devez débloquer la mise en relation. Cela coûte 500 FCFA payables via CinetPay. Une fois le paiement effectué, vous aurez accès aux coordonnées du propriétaire et pourrez échanger avec lui. 📞"
    
    elif user_role == 'owner':
        if 'publier' in message_lower or 'annonce' in message_lower:
            return "Vous pouvez publier vos annonces gratuitement après avoir validé votre identité. Assurez-vous d'avoir complété la vérification d'identité dans votre dashboard, puis allez dans 'Mes propriétés' pour ajouter votre bien. 📸"
        elif 'vérification' in message_lower or 'identité' in message_lower:
            return "La vérification d'identité est obligatoire pour publier des biens sur DOMIORA. Allez dans votre dashboard, section 'Vérification d'identité', et téléchargez vos documents (CNI, passeport). L'administrateur validera votre demande sous 24-48h. ✅"
    
    # If properties were found
    if properties and properties.exists():
        results = []
        for prop in properties[:3]:
            results.append(f"🏠 {prop.title} - {prop.price_display} à {prop.city}")
        return f"J'ai trouvé {len(results)} logements correspondants à votre recherche:\n" + "\n".join(results) + "\n\nVoulez-vous plus de détails sur l'un d'eux ?"
    
    # General fallback with DOMIORA context
    return "Je suis l'assistant DOMIORA et je suis là pour vous aider avec vos questions immobilières. Sur DOMIORA, vous pouvez consulter librement les annonces et contacter les propriétaires après paiement des frais de mise en relation (500 FCFA). Que puis-je faire pour vous ? 🏠"
