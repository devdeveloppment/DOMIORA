"""
AI Assistant Service for DOMIORA
Intelligent context-aware assistant using Mistral API
"""
import json
import re
import logging
import requests
from django.conf import settings
from properties.models import Property

logger = logging.getLogger(__name__)

# Contexte métier de DOMIORA (fonctionnement réel, FedaPay explicitement nommé)
from services.assistant_knowledge import SYSTEM_PROMPT  # noqa: E402


def extract_search_criteria(message):
    """
    Extract property search criteria from message using local fallback if Mistral unavailable
    Returns: dict with criteria (city, bedrooms, budget, etc.) or None
    """
    # First try Mistral if available - TEMPORARILY DISABLED DUE TO MISSING mistralai PACKAGE
    # api_key = getattr(settings, 'MISTRAL_API_KEY', '')
    # if api_key:
    #     try:
    #         prompt = f"""
    #         Analyse ce message utilisateur et extrais les critères de recherche immobilière s'ils sont présents.
    #         Message: "{message}"
    #         
    #         Si le message ne concerne PAS une recherche de logement, retourne "NO_SEARCH".
    #         
    #         Si c'est une recherche, retourne un JSON avec ces champs (null si non spécifié):
    #         {{
    #             "city": "ville ou null",
    #             "bedrooms": nombre ou null,
    #             "budget": "montant ou null",
    #             "property_type": "apartment/house/studio/villa ou null",
    #             "transaction_type": "rent/sale ou null"
    #         }}
    #         
    #         Retourne UNIQUEMENT le JSON, sans autre texte.
    #         """
    #         
    #         # client = Mistral(api_key=api_key)  # Commented out temporarily - mistralai not installed
    #         # response = client.chat.complete(
    #         #     model=getattr(settings, 'MISTRAL_MODEL', 'mistral-small-latest'),
    #         #     messages=[{"role": "user", "content": prompt}],
    #         #     temperature=0.1,
    #         #     max_tokens=200,
    #         #     timeout_ms=10000,
    #         # )

    #         # result = response.choices[0].message.content.strip()

    #         # if "NO_SEARCH" in result:
    #         #     return None

    #         # # Parse JSON
    #         # try:
    #         #     criteria = json.loads(result)
    #         #     return criteria
    #         # except json.JSONDecodeError:
    #         #     logger.warning(f"Failed to parse criteria JSON: {result}")
        
    #     # except Exception as e:
    #     #     logger.error(f"Mistral extraction error, using fallback: {str(e)}")
    
    # Fallback: local pattern matching
    return extract_search_criteria_fallback(message)


def extract_search_criteria_fallback(message):
    """
    Fallback method to extract search criteria using pattern matching
    Returns: dict with criteria or None
    """
    message_lower = message.lower()
    criteria = {}
    
    # Check if this is a search query
    search_keywords = ['cherche', 'recherche', 'trouve', 'veux', 'aimerais', 'cherche', 'looking for']
    if not any(k in message_lower for k in search_keywords):
        return None
    
    # Extract city
    cities = ['lome', 'lomé', 'tokoin', 'bè', 'kedo', 'sokodé', 'kara', 'atakpamé', 'sokode', 'paris', 'abidjan', 'accra']
    for city in cities:
        if city in message_lower:
            criteria['city'] = city
            break
    
    # Extract bedrooms
    import re
    bedroom_patterns = [
        r'(\d+)\s*chambre',
        r'(\d+)\s*ch',
        r'(\d+)\s*bedroom',
        r'(\d+)\s*piece',
    ]
    for pattern in bedroom_patterns:
        match = re.search(pattern, message_lower)
        if match:
            criteria['bedrooms'] = int(match.group(1))
            break
    
    # Extract property type
    property_types = {
        'appartement': 'apartment',
        'apartment': 'apartment',
        'maison': 'house',
        'house': 'house',
        'villa': 'villa',
        'studio': 'studio',
        'terrain': 'terrain',
        'duplex': 'duplex',
    }
    for french_type, english_type in property_types.items():
        if french_type in message_lower:
            criteria['property_type'] = english_type
            break
    
    # Extract transaction type
    if 'louer' in message_lower or 'location' in message_lower:
        criteria['transaction_type'] = 'rent'
    elif 'acheter' in message_lower or 'vente' in message_lower or 'a vendre' in message_lower:
        criteria['transaction_type'] = 'sale'
    
    # Extract budget (basic pattern)
    budget_patterns = [
        r'(\d+)\s*fcfa',
        r'(\d+)\s*f\s*cfa',
        r'budget\s*(\d+)',
        r'(\d+)\s*xof',
    ]
    for pattern in budget_patterns:
        match = re.search(pattern, message_lower)
        if match:
            criteria['budget'] = match.group(1)
            break
    
    # Only return criteria if we found something meaningful
    if len(criteria) > 0:
        return criteria
    
    return None


def search_properties_with_criteria(criteria):
    """
    Search properties based on extracted criteria.

    Délègue au moteur de recherche intelligent (services.property_search), qui
    applique la règle de visibilité publique (_public_contactable_properties),
    la disponibilité, la vérification du propriétaire et le budget.
    Returns: QuerySet of Property objects (max 5, ordered by relevance)
    """
    from services.property_search import legacy_search

    return legacy_search(criteria, limit=5)


def generate_intelligent_response(message, properties=None, conversation_history=None, user_role=None):
    """
    Generate intelligent response using Mistral with context awareness and role
    
    Args:
        message: User message
        properties: QuerySet of properties (if search was performed)
        conversation_history: List of previous messages for context
        user_role: User role - 'visitor', 'owner', or 'admin'
    
    Returns: str - Natural intelligent response
    """
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
    
    # Build role context
    role_context = ""
    if user_role:
        role_mapping = {
            'visitor': 'Client / Visiteur',
            'owner': 'Propriétaire',
            'admin': 'Administrateur'
        }
        role_context = f"\n\nRôle de l'utilisateur: {role_mapping.get(user_role, user_role)}"
    
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}{context}{role_context}"}]
    for item in (conversation_history or [])[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()[:2000]
        if content and not (role == "user" and content == message.strip()):
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message.strip()[:4000]})

    providers = []
    mistral_key = getattr(settings, "MISTRAL_API_KEY", "")
    if mistral_key:
        providers.append(("Mistral", lambda: _request_mistral(mistral_key, messages)))

    anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if anthropic_key:
        providers.append(("Anthropic", lambda: _request_anthropic(anthropic_key, messages)))

    for provider_name, request_response in providers:
        try:
            reply = request_response()
            if reply:
                logger.info("Assistant response generated with %s", provider_name)
                return _sanitize_payment_provider_names(reply)
            raise ValueError("The provider returned an empty response")
        except Exception as error:
            logger.warning("Assistant provider %s failed (%s)", provider_name, type(error).__name__)

    return _generate_fallback_response(message, properties, user_role)


def _request_mistral(api_key, messages):
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": getattr(settings, "MISTRAL_MODEL", "mistral-small-latest"),
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 800,
        },
        timeout=(5, 20),
    )
    response.raise_for_status()
    choices = response.json().get("choices", [])
    if not choices:
        return ""
    return (choices[0].get("message", {}).get("content") or "").strip()


def _request_anthropic(api_key, messages):
    system_message = messages[0]["content"]
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": getattr(settings, "ANTHROPIC_MODEL", "claude-haiku-4-5"),
            "system": system_message,
            "messages": messages[1:],
            "temperature": 0.4,
            "max_tokens": 800,
        },
        timeout=(5, 20),
    )
    response.raise_for_status()
    content = response.json().get("content", [])
    return "\n".join(
        block.get("text", "").strip()
        for block in content
        if block.get("type") == "text" and block.get("text", "").strip()
    )


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
    
    # Step 1: Extract search criteria using Mistral with fallback
    criteria = extract_search_criteria(message)
    
    # Step 2: Search properties if criteria found
    properties = None
    if criteria:
        logger.info(f"Search criteria extracted: {criteria}")
        properties = search_properties_with_criteria(criteria)
    
    # Step 3: Generate intelligent response with context and role
    response = _sanitize_payment_provider_names(
        generate_intelligent_response(message, properties, conversation_history, user_role)
    )
    
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
    """Fallback responses when Mistral is unavailable with role awareness"""
    message_lower = message.lower()
    
    # Check for greetings
    greetings = ['bonjour', 'salut', 'hello', 'hi', 'coucou', 'bonsoir', 'bienvenue', 'hey']
    if any(g in message_lower for g in greetings):
        return "Bonjour ! Je suis l'assistant DOMIORA. Comment puis-je vous aider aujourd'hui ?"
    
    # Check for how are you
    how_are_you = ['comment ça va', 'comment vas-tu', 'ça va', 'tu vas', 'comment allez-vous']
    if any(h in message_lower for h in how_are_you):
        return "Je vais très bien merci. Je suis l'assistant DOMIORA et je suis là pour vous aider à trouver un logement ou répondre à vos questions. Et vous, comment allez-vous ?"
    
    # Check for thanks
    thanks = ['merci', 'thanks', 'thank you']
    if any(t in message_lower for t in thanks):
        return "Je vous en prie ! N'hésitez pas si vous avez d'autres questions."
    
    # Check for goodbye
    goodbye = ['au revoir', 'bye', 'a bientot', 'a plus']
    if any(g in message_lower for g in goodbye):
        return "Au revoir ! N'hésitez pas à revenir si vous avez d'autres questions sur DOMIORA."
    
    # Check for who are you
    who_are_you = ['qui es-tu', 'qui etes vous', "c'est quoi domiora", "qu'est-ce que domiora"]
    if any(w in message_lower for w in who_are_you):
        return "Je suis l'assistant intelligent de DOMIORA, une plateforme immobilière qui connecte propriétaires et clients. Les propriétaires peuvent publier gratuitement leurs annonces après vérification d'identité, et les clients peuvent consulter les biens librement et contacter les propriétaires contre 500 FCFA de frais de mise en relation."

    # Explain identity verification before the generic "how it works" response.
    identity_terms = ['vérification', 'verification', 'identité', 'identite', 'pièce d\'identité', 'piece d\'identite', 'cni', 'passeport']
    if any(term in message_lower for term in identity_terms):
        return "La vérification d'identité est obligatoire pour les propriétaires qui souhaitent publier un bien sur DOMIORA. Depuis votre espace propriétaire, ouvrez la section « Vérification d'identité », choisissez le type de document, puis envoyez une pièce d'identité valide et lisible, comme une CNI ou un passeport. L'administrateur vérifie ensuite les documents. La validation prend généralement 24 à 48 heures. Après validation, vous pouvez publier vos annonces gratuitement."
    
    # Check for how it works
    how_it_works = ['comment ça marche', 'comment fonctionne', 'comment ca marche']
    if any(h in message_lower for h in how_it_works):
        return "DOMIORA fonctionne simplement : en tant que visiteur, vous pouvez consulter toutes les annonces gratuitement. Lorsque vous souhaitez contacter un proprietaire ou demander une visite, vous payez 500 FCFA via un paiement securise pour debloquer la mise en relation. Les proprietaires doivent verifier leur identite avant de publier gratuitement leurs annonces."
    
    # Check for visit virtuelle specifically
    if 'visite virtuelle' in message_lower:
        return "La visite virtuelle sur DOMIORA permet de voir les biens en detail sans vous deplacer. Les proprietaires peuvent ajouter des photos et des videos 360 degres pour presenter leurs logements de maniere immersive. Vous pouvez consulter toutes les visites virtuelles gratuitement avant de contacter le proprietaire."
    
    # Role-specific responses for visitors
    if user_role == 'visitor' or user_role is None:
        if 'compte' in message_lower and ('créer' in message_lower or 'inscription' in message_lower or 'sinscrire' in message_lower):
            return "Sur DOMIORA, vous n'avez pas besoin de creer un compte pour consulter les biens. Vous pouvez parcourir toutes les annonces librement. Lorsque vous souhaitez contacter un proprietaire ou demander une visite, il suffit de debloquer la mise en relation (500 FCFA via un paiement securise)."
        elif 'contacter' in message_lower or 'propriétaire' in message_lower or 'proprietaire' in message_lower:
            return "Pour contacter un proprietaire sur DOMIORA, vous devez debloquer la mise en relation. Cela coute 500 FCFA via un paiement securise. Une fois le paiement effectue, vous aurez acces aux coordonnees du proprietaire et pourrez echanger avec lui."
        elif 'frais' in message_lower or 'prix' in message_lower or 'cout' in message_lower or 'coût' in message_lower:
            return "Les frais de mise en relation sur DOMIORA sont de 500 FCFA. Ce montant unique vous donne acces aux coordonnees du proprietaire et permet d'echanger avec lui pour organiser des visites."
        elif 'paiement' in message_lower or 'payer' in message_lower:
            return "Les frais de mise en relation sont payables via un paiement securise. Les moyens de paiement disponibles s'affichent au moment de la validation."
        elif 'photo' in message_lower or 'image' in message_lower:
            return "Oui, vous pouvez voir toutes les photos et videos des biens gratuitement sur DOMIORA avant de decider de contacter le proprietaire. Il n'y a pas besoin de payer pour consulter les annonces."
        elif 'payer' in message_lower and 'frais' in message_lower:
            return "Pour payer les frais de mise en relation, cliquez sur le bouton 'Contacter' ou 'Demander une visite' sur une annonce. Vous serez redirige vers l'interface de paiement securisee pour regler les 500 FCFA."
    
    # Role-specific responses for owners
    if user_role == 'owner':
        if 'publier' in message_lower or 'annonce' in message_lower:
            return "Vous pouvez publier vos annonces gratuitement apres avoir valide votre identite. Assurez-vous d'avoir complete la verification d'identite dans votre dashboard, puis allez dans 'Mes proprietes' pour ajouter votre bien."
        elif 'vérification' in message_lower or 'identité' in message_lower or 'identite' in message_lower:
            return "La verification d'identite est obligatoire pour publier des biens sur DOMIORA. Allez dans votre dashboard, section 'Verification d'identite', et telechargez vos documents (CNI, passeport). L'administrateur validera votre demande sous 24-48h."
        elif 'document' in message_lower:
            return "Pour la verification d'identite, vous devez fournir une piece d'identite valide (CNI, passeport ou carte d'identite nationale). Assurez-vous que le document est lisible et en couleur."
        elif 'gratuit' in message_lower:
            return "Oui, la publication d'annonces est entierement gratuite sur DOMIORA apres validation de votre identite. Il n'y a aucun frais pour ajouter vos biens."
        elif 'combien' in message_lower and ('temps' in message_lower or 'jour' in message_lower):
            return "La validation d'identite prend generalement 24 a 48 heures. Une fois valide, vous pourrez publier vos annonces immediatement."
        elif 'mettre' in message_lower and ('location' in message_lower or 'louer' in message_lower):
            return "Pour mettre votre bien en location, allez dans votre dashboard proprietaire, section 'Mes proprietes', cliquez sur 'Ajouter une propriete' et selectionnez 'Location' comme type de transaction. Remplissez les details de votre bien et ajoutez des photos."
    
    # Role-specific responses for admin
    if user_role == 'admin':
        if 'valider' in message_lower or 'validation' in message_lower:
            return "Pour valider un proprietaire, allez dans votre dashboard administrateur, section 'Validations en attente'. Vous pouvez consulter les documents soumis et accepter ou refuser chaque demande."
        if 'inscription' in message_lower or 'nouveau' in message_lower:
            return "Les nouvelles inscriptions apparaissent dans votre dashboard administrateur. Vous recevez une notification pour chaque nouvelle demande de validation de proprietaire."
        if 'verifier' in message_lower and 'document' in message_lower:
            return "Pour verifier les documents d'identite, accedez a la demande de validation depuis votre dashboard admin. Vous pouvez zoomer sur les documents, verifier leur authenticite et comparer avec les informations du profil."
        if 'faux' in message_lower and 'document' in message_lower:
            return "Si un proprietaire a soumis des faux documents, refusez la validation avec la raison 'Documents falsifies' et signalez le compte. Le compte sera bloque et l'utilisateur ne pourra plus soumettre de demandes."
    
    # If properties were found
    if properties and properties.exists():
        results = []
        for prop in properties[:3]:
            results.append(f"- {prop.title} - {prop.price_display} a {prop.city}")
        return f"J'ai trouve {len(results)} logements correspondants a votre recherche:\n" + "\n".join(results) + "\n\nVoulez-vous plus de details sur l'un d'eux ?"
    
    # Explain how to find a property
    how_to_find_property = (
        ('comment' in message_lower or 'ou' in message_lower)
        and any(term in message_lower for term in ['trouver', 'trouvez', 'chercher', 'cherchez'])
        and any(term in message_lower for term in ['bien', 'logement', 'propriete', 'propriété', 'annonce'])
    )
    if how_to_find_property:
        return "Pour trouver un bien sur DOMIORA, utilisez la barre de recherche ou les filtres pour choisir la ville, le type de bien, le budget et le nombre de chambres. Ouvrez ensuite une annonce pour consulter ses photos, sa description, son prix et ses caractéristiques. Vous pouvez voir les annonces librement. Pour contacter le propriétaire ou demander une visite, cliquez sur le bouton prévu et débloquez la mise en relation pour 500 FCFA via un paiement sécurisé."

    # Search-related fallback
    if 'cherche' in message_lower or 'recherche' in message_lower or 'trouver' in message_lower:
        return "Je peux vous aider a trouver un logement. Dites-moi ce que vous recherchez : ville, type de bien (appartement, maison, villa), nombre de chambres, budget, etc. Je chercherai les annonces correspondantes sur DOMIORA."
    
    # Support questions
    if 'oubli' in message_lower and 'mot de passe' in message_lower:
        return "Si vous avez oublie votre mot de passe, utilisez la fonction 'Mot de passe oublie' sur la page de connexion. Un lien de reinitialisation vous sera envoye par email."
    if 'probleme' in message_lower or 'signaler' in message_lower:
        return "Pour signaler un probleme, vous pouvez nous contacter via le formulaire de contact sur le site ou envoyer un email a notre support. Nous traitons toutes les demandes rapidement."
    if 'repond' in message_lower and 'proprietaire' in message_lower:
        return "Si un proprietaire ne repond pas, assurez-vous d'abord que le paiement a bien ete effectue. Si c'est le cas, vous pouvez relancer le message via la messagerie de votre espace client ou nous contacter pour assistance."
    
    # Additional specific responses
    if 'orange money' in message_lower or 'mtn' in message_lower or 'moov' in message_lower:
        return "Les moyens de paiement disponibles peuvent inclure le mobile money et les cartes bancaires, selon les options proposées lors du paiement."
    
    if 'pays' in message_lower and ('disponible' in message_lower or 'autre' in message_lower):
        return "DOMIORA est principalement disponible au Togo et dans les pays voisins. Nous travaillons a etendre notre presence a d'autres pays de la region."
    
    if 'terrain' in message_lower:
        return "Oui, vous pouvez trouver des terrains a vendre sur DOMIORA. Utilisez les filtres de recherche et selectionnez 'Terrain' comme type de bien."
    
    if 'securite' in message_lower and 'paiement' in message_lower:
        return "Les paiements sur DOMIORA sont traites via une interface securisee. Vos informations bancaires sont protegees et ne sont jamais stockees sur nos serveurs."
    
    if 'modifier' in message_lower and 'annonce' in message_lower:
        return "Pour modifier votre annonce, connectez-vous a votre dashboard proprietaire, allez dans 'Mes proprietes', cliquez sur l'annonce a modifier, puis sur 'Modifier'."
    
    if 'supprimer' in message_lower and 'annonce' in message_lower:
        return "Pour supprimer votre annonce, allez dans votre dashboard proprietaire, section 'Mes proprietes', cliquez sur l'annonce et choisissez 'Supprimer'. Attention, cette action est irreversible."
    
    if 'ajouter' in message_lower and 'photo' in message_lower:
        return "Pour ajouter des photos a votre annonce, modifiez votre propriete depuis votre dashboard et cliquez sur 'Ajouter des photos'. Vous pouvez ajouter jusqu'a 20 photos par annonce."
    
    if 'frauduleuse' in message_lower or 'arnaque' in message_lower:
        return "Pour signaler une annonce frauduleuse, utilisez le bouton 'Signaler' sur la page de l'annonce ou contactez notre support. Nous investiguerons rapidement et prendrons les mesures necessaires."
    
    if 'paye' in message_lower and 'acces' in message_lower:
        return "Si vous avez paye mais n'avez pas acces au proprietaire, verifiez d'abord que le paiement a ete confirme. Si le probleme persiste, contactez notre support avec votre numero de transaction."
    
    if 'visite' in message_lower and 'sans payer' in message_lower:
        return "Les visites virtuelles (photos et videos) sont gratuites a consulter. Pour une visite physique ou contacter le proprietaire, les frais de mise en relation de 500 FCFA s'appliquent."
    
    if 'changer' in message_lower and 'mot de passe' in message_lower:
        return "Pour changer votre mot de passe, connectez-vous a votre compte, allez dans 'Mon profil' ou 'Parametres', puis cliquez sur 'Changer le mot de passe'. Vous devrez entrer votre mot de passe actuel et le nouveau."
    
    # General fallback with DOMIORA context
    return "Je suis l'assistant DOMIORA et je suis la pour vous aider avec vos questions immobilieres. Sur DOMIORA, vous pouvez consulter librement les annonces et contacter les proprietaires apres paiement des frais de mise en relation (500 FCFA). Que puis-je faire pour vous ?"


def _sanitize_payment_provider_names(response):
    """FedaPay est le seul moyen de paiement : toute mention d'un autre prestataire est remplacée."""
    return re.sub(r"(?i)\b(cinetpay|paydunya|stripe|paypal)\b", "FedaPay", response or "")


# ===========================================================================
# Assistant DOMIORA conversationnel (bloc C)
#
# - L'état de conversation est conservé côté serveur (session) : critères de
#   recherche, biens présentés (numérotés), sélection, bien « en cours ».
# - Les biens viennent exclusivement de services.property_search (bloc B) et
#   la comparaison de services.property_compare.
# - Visites et mises en relation : l'assistant oriente vers les mécanismes
#   existants (FedaPay, messagerie) sans jamais rien débloquer ni créer.
# - Le LLM (Mistral → Anthropic) ne sert qu'à comprendre les critères et à
#   répondre aux questions générales ; sans fournisseur, des réponses locales
#   prennent le relais.
# ===========================================================================
import copy  # noqa: E402

from services import assistant_knowledge as knowledge  # noqa: E402
from services import llm as llm_service  # noqa: E402
from services import property_compare, property_search  # noqa: E402
from services.property_search import normalize  # noqa: E402

MAX_CARDS = 5
MAX_HISTORY = 10

_ORDINALS = {
    "premier": 0, "premiere": 0, "1er": 0, "1re": 0, "1ere": 0,
    "deuxieme": 1, "second": 1, "seconde": 1, "2e": 1, "2eme": 1, "2nd": 1, "2nde": 1,
    "troisieme": 2, "3e": 2, "3eme": 2,
    "quatrieme": 3, "4e": 3, "4eme": 3,
    "cinquieme": 4, "5e": 4, "5eme": 4,
    "dernier": -1, "derniere": -1,
}
_COUNT_WORDS = {"deux": 2, "2": 2, "trois": 3, "3": 3, "quatre": 4, "4": 4, "cinq": 5, "5": 5}
_FOCUS_RE = re.compile(
    r"\b(celle|celui)[- ](la|ci)\b|\bce bien\b|\bce logement\b|\bcette (maison|villa|annonce|propriete|offre)\b"
    r"|\bcet appartement\b|\bce studio\b|\b(le|la) (visiter|contacter|voir|reserver)\b|\bl'(visiter|avoir)\b"
)
_QUESTION_RE = re.compile(r"^(comment|pourquoi|c'est quoi|qu'est[- ]ce|est[- ]ce que|combien|quel est|quelle est|ou |a quoi|que faire)|\?\s*$")
_REFINE_RE = re.compile(r"\b(seulement|uniquement|plutot|et avec|et sans|sans|avec|aussi|plus grand|plus grande|que les|juste les)\b")
_CHEAPER_RE = re.compile(r"\b(moins cher|moins chere|moins chers|moins cheres|plus abordable|plus abordables|moins couteux|budget plus bas)\b")
_COMPARE_RE = re.compile(r"\bcompar")
_VISIT_RE = re.compile(r"\b(visiter|visite|rendez-vous|rdv)\b")
_CONTACT_RE = re.compile(r"\b(contacter|joindre|appeler|ecrire au proprietaire|parler au proprietaire|mise en relation|mettre en relation)\b")
_PRIVATE_RE = re.compile(r"\b(numero|telephone|tel|whatsapp|email|e-mail|mail|coordonnees|adresse email)\b")
_SELECT_RE = re.compile(r"\b(montre|montrez|affiche|affichez|voir|details?|detaille|prefere|choisis|retiens|garde|interesse|infos?|plus d'informations)\b")
_PAYMENT_CLAIM_RE = re.compile(r"\b(j'?ai (deja )?(paye|regle|effectue le paiement|fait le paiement)|paiement (est )?(effectue|fait|valide|termine)|deja paye)\b")
_LIST_RE = re.compile(r"\b(quels biens|quels sont les biens|biens disponibles|qu'avez[- ]vous|que proposez[- ]vous|vous avez quoi|tous les biens)\b")
_GREETING_RE = re.compile(r"^(bonjour|bonsoir|salut|hello|coucou|hey|bjr|slt)\b")
_THANKS_RE = re.compile(r"\b(merci|thanks|parfait|super|genial)\b")
_BYE_RE = re.compile(r"\b(au revoir|a bientot|bye|bonne journee|bonne soiree)\b")
_HUMAN_RE = re.compile(r"\b(es[- ]tu|etes[- ]vous|tu es|vous etes) (un |une )?(humain|robot|ia|vrai|personne|bot)\b|\bqui (es[- ]tu|etes[- ]vous)\b")

_FAQ_TOPICS = [
    ("not_published", r"(pas (encore )?(publie|en ligne|visible)|n'est pas (encore )?(publie|visible|en ligne)|toujours en attente|pas apparu)"),
    ("why_pay", r"pourquoi .*(payer|frais|paie|500)"),
    ("payment", r"(fedapay|moyens? de paiement|comment (je )?pa(yer|ie)|mobile money|payer par|paiement)"),
    ("verification", r"(verification|verifie|verifier|identite|cni|passeport|agent de verification|badge)"),
    ("become_owner", r"(devenir proprietaire|compte proprietaire|inscrire comme proprietaire|inscription proprietaire)"),
    ("publish", r"(publier|mettre en ligne|deposer une annonce|ajouter (un|mon) bien|poster)"),
    ("virtual_tour", r"(visite virtuelle|video)"),
    ("ai_search", r"(recherche (ia|intelligente|avec l'ia)|fonctionne la recherche)"),
    ("compare", r"(comparateur|comment comparer)"),
    ("alerts", r"(alerte)"),
    ("visit", r"(visite|visiter|rendez-vous)"),
    ("contact", r"(contacter|joindre|mise en relation|mettre en relation|coordonnees|numero|telephone)"),
    ("how_it_works", r"(comment (ca )?(marche|fonctionne)|c'est quoi domiora|qu'est[- ]ce que domiora|fonctionnement|domiora)"),
    ("find_property", r"(trouver|chercher|rechercher)"),
]
_NON_SEARCH_TOPICS = {"not_published", "why_pay", "payment", "verification", "become_owner", "publish", "ai_search", "alerts"}
_STRONG_KEYS = (
    "property_kind", "city", "budget_min", "budget_max", "bedrooms", "features",
    "transaction_type", "surface_min", "surface_max", "bathrooms_min",
)
_QUICK_REPLIES_BY_QUESTION = {
    "location": ["Lomé", "Kara", "Peu importe"],
    "kind_location": ["Un appartement à Lomé", "Une maison à Lomé", "Un terrain"],
    "budget": ["100 000 FCFA", "250 000 FCFA", "Peu importe"],
    "bedrooms": ["1", "2", "3", "Peu importe"],
}


def new_assistant_state():
    return {
        "search": property_search.new_state(),
        "presented_ids": [],
        "selection_ids": [],
        "focus_id": None,
        "history": [],
        "hint_shown": False,
    }


def _load_state(state):
    base = new_assistant_state()
    if isinstance(state, dict):
        for key in base:
            if key in state:
                base[key] = copy.deepcopy(state[key])
    return base


# ---------------------------------------------------------------------------
# Compréhension
# ---------------------------------------------------------------------------
def parse_references(text):
    """
    Repère les références aux biens déjà présentés.
    Retourne {"indexes": [...], "focus": bool, "count": n|None}.
    """
    indexes = []
    count = None
    group = re.search(r"\bles (deux|2|trois|3|quatre|4|cinq|5) (premiers?|premieres?|derniers?|dernieres?)\b", text)
    if group:
        n = _COUNT_WORDS[group.group(1)]
        count = n
        indexes = list(range(n)) if group.group(2).startswith("premi") else list(range(-n, 0))
    else:
        for match in re.finditer(r"\b(" + "|".join(sorted(_ORDINALS, key=len, reverse=True)) + r")\b", text):
            idx = _ORDINALS[match.group(1)]
            if idx not in indexes:
                indexes.append(idx)
        for match in re.finditer(r"\b(?:numero|n°|no|bien|annonce|resultat)\s*(\d)\b", text):
            idx = int(match.group(1)) - 1
            if idx >= 0 and idx not in indexes:
                indexes.append(idx)
        both = re.search(r"\b(les deux|les 2|tous les deux|toutes les deux)\b", text)
        if both and not indexes:
            count = 2
    return {"indexes": indexes, "focus": bool(_FOCUS_RE.search(text)), "count": count}


def _strong_criteria(message):
    delta, flags = property_search.extract_rules(message)
    return {k: v for k, v in delta.items() if k in _STRONG_KEYS and v}, flags


def detect_intent(message, state):
    """Retourne (intent, refs, topic). Déterministe : le LLM n'arbitre jamais les actions."""
    text = normalize(message)
    refs = parse_references(text)
    has_refs = bool(refs["indexes"] or refs["focus"] or refs["count"])
    has_results = bool(state["presented_ids"])
    is_question = bool(_QUESTION_RE.search(text))
    strong, flags = _strong_criteria(message)

    if flags["reset"]:
        return "reset", refs, None
    if _PAYMENT_CLAIM_RE.search(text):
        return "payment_claim", refs, None
    if _COMPARE_RE.search(text) and (has_results or has_refs) and "comparateur" not in text:
        return "compare", refs, None
    if _VISIT_RE.search(text) and "virtuelle" not in text and "video" not in text:
        if has_refs or (has_results and not is_question) or (state["focus_id"] and not is_question):
            return "visit", refs, None
    if _CONTACT_RE.search(text) or (_PRIVATE_RE.search(text) and "proprietaire" in text):
        if has_refs or (state["focus_id"] and not is_question) or (len(state["presented_ids"]) == 1 and not is_question):
            return "contact", refs, None
    if has_results and (refs["indexes"] or refs["focus"]) and (_SELECT_RE.search(text) or len(text.split()) <= 4):
        return "select", refs, None

    # Questions sur le fonctionnement de DOMIORA
    topic = next((name for name, pattern in _FAQ_TOPICS if re.search(pattern, text)), None)
    beyond_kind = set(strong) - {"property_kind", "transaction_type"}
    concrete_search = (bool(strong) and not is_question) or (bool(beyond_kind) and flags["is_search"])
    if topic and (is_question or topic in _NON_SEARCH_TOPICS) and not concrete_search:
        if topic != "find_property" or not strong.keys() - {"property_kind"}:
            return "faq", refs, topic

    criteria = state["search"]["criteria"]
    has_criteria = any(criteria.get(k) for k in _STRONG_KEYS)
    if _CHEAPER_RE.search(text) and (has_criteria or has_results):
        return "cheaper", refs, None
    if _LIST_RE.search(text):
        return "search_list", refs, None
    if strong and (flags["is_search"] or not is_question or has_criteria):
        return "search", refs, None
    if state["search"].get("pending") and not is_question and len(text.split()) <= 6:
        return "search", refs, None
    if has_criteria and (_REFINE_RE.search(text) or flags["removed_features"] or flags["show_now"]):
        return "search", refs, None

    if _HUMAN_RE.search(text):
        return "faq", refs, "identity"
    if _GREETING_RE.search(text) and len(text.split()) <= 4:
        return "greeting", refs, None
    if _BYE_RE.search(text):
        return "bye", refs, None
    if _THANKS_RE.search(text) and len(text.split()) <= 5:
        return "thanks", refs, None
    if flags["is_search"] and not is_question:
        return "search", refs, None
    return "general", refs, None


# ---------------------------------------------------------------------------
# Accès aux biens présentés (toujours revalidés par la règle de visibilité)
# ---------------------------------------------------------------------------
def _visible_by_ids(ids):
    if not ids:
        return []
    found = {
        p.pk: p
        for p in property_search.visible_properties().filter(pk__in=ids).select_related("owner").prefetch_related("images", "amenities")
    }
    return [found[i] for i in ids if i in found]


def _resolve(refs, state, default_all=False):
    """
    Traduit les références en ids de biens présentés.
    Retourne (ids, erreur_texte|None).
    """
    presented = state["presented_ids"]
    if refs["indexes"]:
        ids, missing = [], []
        for idx in refs["indexes"]:
            if -len(presented) <= idx < len(presented):
                ids.append(presented[idx])
            else:
                missing.append(idx + 1)
        if missing:
            if not presented:
                return [], "Je n'ai pas encore présenté de biens. Dites-moi ce que vous recherchez et je lance la recherche."
            return [], f"Je n'ai présenté que {len(presented)} bien{'s' if len(presented) > 1 else ''} : indiquez par exemple « le premier »."
        return list(dict.fromkeys(ids)), None
    if refs["count"]:
        base = state["selection_ids"] if len(state["selection_ids"]) >= refs["count"] else presented
        return base[: refs["count"]], None
    if refs["focus"] and state["focus_id"]:
        return [state["focus_id"]], None
    if state["focus_id"] and not default_all:
        return [state["focus_id"]], None
    if len(state["selection_ids"]) == 1:
        return state["selection_ids"], None
    if len(presented) == 1:
        return presented, None
    if default_all:
        return (state["selection_ids"] if len(state["selection_ids"]) >= 2 else presented)[:3], None
    return [], None


def _card(prop, criteria, index=None, alternative=False):
    evaluation = property_search.evaluate(prop, criteria)
    level = property_search.classify(evaluation)
    card = property_search.serialize_property(prop, evaluation, level)
    card["index"] = index
    card["is_alternative"] = alternative
    return card


def _cards_for(ids, state):
    criteria = state["search"]["criteria"]
    presented = state["presented_ids"]
    return [
        _card(p, criteria, index=presented.index(p.pk) + 1 if p.pk in presented else None)
        for p in _visible_by_ids(ids)
    ]


def _label(card_or_prop):
    title = card_or_prop["title"] if isinstance(card_or_prop, dict) else card_or_prop.title
    return f"« {title} »"


# ---------------------------------------------------------------------------
# Orientation vers les mécanismes existants (aucune action effectuée ici)
# ---------------------------------------------------------------------------
def connection_route(user, prop, purpose):
    """
    Indique comment visiter / contacter, selon les règles existantes :
    paiement FedaPay (par propriétaire) puis messagerie.
    Retourne (texte, actions).
    """
    from django.urls import reverse

    from accounts.models import User
    from messaging.models import Conversation
    from messaging.views import _has_paid_for_property

    goal = "demander une visite de" if purpose == "visit" else "contacter le propriétaire de"
    view = {"label": "Voir le bien", "url": prop.get_absolute_url(), "kind": "link"}
    pay = {
        "label": "Débloquer la mise en relation",
        "url": reverse("properties:payment_redirect", args=[prop.slug]),
        "kind": "primary",
    }
    unlock_text = (
        f"il faut d'abord débloquer la mise en relation avec son propriétaire : {knowledge.CONNECTION_FEE}, payés via FedaPay. "
        "Ce déblocage est valable pour tous les biens de ce propriétaire."
    )

    if not user or not user.is_authenticated:
        return (
            f"Pour {goal} {_label(prop)}, {unlock_text} Vous pourrez ensuite échanger avec lui depuis votre espace client"
            + (" et proposer une date de visite." if purpose == "visit" else "."),
            [pay, view],
        )
    if user.role != User.Role.CLIENT:
        return (
            "Les demandes de visite et la mise en relation se font depuis un compte client. "
            "Vous êtes actuellement connecté avec un compte " + user.get_role_display().lower() + ".",
            [view],
        )
    if not _has_paid_for_property(user, prop):
        return (
            f"Vous n'avez pas encore de mise en relation active avec le propriétaire de {_label(prop)}. "
            f"Pour {'demander une visite' if purpose == 'visit' else 'le contacter'}, {unlock_text}",
            [pay, view],
        )

    conversation = Conversation.objects.filter(buyer=user, owner=prop.owner, property=prop).first()
    start = {
        "label": "Ouvrir la conversation",
        "url": reverse("messaging:start_conversation", args=[prop.owner_id]) + f"?property={prop.pk}",
        "kind": "primary",
    }
    if purpose == "visit":
        if conversation:
            return (
                f"Votre mise en relation avec ce propriétaire est active. Vous pouvez demander une visite de {_label(prop)} ici : "
                "proposez une date, le propriétaire pourra l'accepter ou en proposer une autre.",
                [
                    {"label": "Demander une visite", "url": reverse("messaging:request_visit", args=[conversation.pk]), "kind": "primary"},
                    view,
                ],
            )
        return (
            f"Votre mise en relation avec ce propriétaire est active. Ouvrez la conversation au sujet de {_label(prop)}, "
            "puis cliquez sur « Demander une visite » pour proposer une date.",
            [start, view],
        )
    if conversation:
        start = {
            "label": "Ouvrir la conversation",
            "url": reverse("dashboard:client_conversation_detail", args=[conversation.pk]),
            "kind": "primary",
        }
    return (
        f"Votre mise en relation avec ce propriétaire est active : vous pouvez lui écrire au sujet de {_label(prop)} depuis la messagerie DOMIORA.",
        [start, view],
    )


# ---------------------------------------------------------------------------
# Traitements par intention
# ---------------------------------------------------------------------------
def _result(reply, intent, **extra):
    data = {
        "reply": reply,
        "intent": intent,
        "cards": [],
        "actions": [],
        "comparison": None,
        "criteria_summary": [],
        "quick_replies": [],
        "source": "local",
    }
    data.update(extra)
    return data


def _present_search(state, search_result, intro=""):
    """Transforme un résultat du moteur de recherche en réponse de chat numérotée."""
    exact = search_result["results"][:MAX_CARDS]
    alternatives = search_result["alternatives"][: 3 - len(exact)] if len(exact) < 3 else []
    cards = []
    for i, item in enumerate(exact + alternatives):
        card = dict(item)
        card["index"] = i + 1
        card["is_alternative"] = i >= len(exact)
        cards.append(card)
    state["presented_ids"] = [c["id"] for c in cards]
    state["selection_ids"] = []
    state["focus_id"] = cards[0]["id"] if len(cards) == 1 else None

    reply = (intro + search_result["message"]).strip()
    if exact and alternatives:
        first_alt = len(exact) + 1
        reply += f" Le bien n°{first_alt} et les suivants sont des alternatives proches." if len(alternatives) > 1 else f" Le bien n°{first_alt} est une alternative proche."
    quick = []
    if len(cards) >= 2:
        quick = ["Compare les deux premiers", "Je veux visiter le premier", "Moins cher"]
    elif len(cards) == 1:
        quick = ["Je veux visiter ce bien", "Comment contacter le propriétaire ?"]
    if len(cards) >= 2 and not state["hint_shown"]:
        reply += "\nVous pouvez me dire par exemple « compare les deux premiers » ou « je veux visiter le deuxième »."
        state["hint_shown"] = True
    return _result(reply, "search", cards=cards, criteria_summary=search_result["criteria_summary"], quick_replies=quick)


def _is_new_search(message):
    """« Je cherche une maison… » : nouvelle recherche explicite (les affinages n'ont pas de verbe de recherche)."""
    strong, flags = _strong_criteria(message)
    return flags["is_search"] and "property_kind" in strong


def _handle_search(message, refs, state, user, use_llm, show_now=False, fresh=False):
    if fresh or _is_new_search(message):
        state["search"] = property_search.new_state()
        state["presented_ids"], state["selection_ids"], state["focus_id"] = [], [], None
    previous = copy.deepcopy(state["search"]["criteria"])
    had_results = bool(state["presented_ids"])
    search_state, result = property_search.run_conversation_turn(state["search"], message, use_llm=use_llm, show_now=show_now)
    state["search"] = search_state

    if result["status"] == "question":
        return _result(
            result["message"],
            "search_question",
            criteria_summary=result["criteria_summary"],
            quick_replies=_QUICK_REPLIES_BY_QUESTION.get(result["question_key"], []),
        )

    current = search_state["criteria"]
    same_search = any(previous.get(k) and previous.get(k) == current.get(k) for k in ("property_kind", "city"))
    intro = "Bien sûr. "
    if had_results and same_search:
        added = [property_search.FEATURES[f][0].lower() for f in current["features"] if f not in previous["features"]]
        intro = "J'ai affiné votre recherche" + (f" : uniquement les biens avec {', '.join(added)}. " if added else ". ")
    return _present_search(state, result, intro)


def _handle_cheaper(message, refs, state, user, use_llm):
    search_state = state["search"]
    criteria = search_state["criteria"]
    presented = _visible_by_ids(state["presented_ids"])
    local_prices = [float(p.price) for p in presented if normalize(p.currency) in property_search.LOCAL_CURRENCIES]
    if local_prices:
        new_max = int(min(local_prices)) - 1
    elif criteria.get("budget_max"):
        new_max = int(criteria["budget_max"] * 0.8)
    else:
        search_state["pending"] = "budget"
        return _result("Bien sûr. Quel budget maximum souhaitez-vous (en FCFA) ?", "search_question",
                       quick_replies=_QUICK_REPLIES_BY_QUESTION["budget"])
    saved_search = copy.deepcopy(search_state)
    criteria["budget_max"] = max(new_max, 1)
    if criteria.get("budget_min") and criteria["budget_min"] > criteria["budget_max"]:
        criteria["budget_min"] = None
    previous_ids = set(state["presented_ids"])
    search_state, result = property_search.search_now(search_state)
    state["search"] = search_state
    # Un bien déjà présenté n'est pas une alternative « moins chère ».
    result["alternatives"] = [a for a in result["alternatives"] if a["id"] not in previous_ids]
    if not result["results"] and not result["alternatives"]:
        # Rien de moins cher : on conserve la recherche et la liste précédentes.
        state["search"] = saved_search
        return _result(
            "Je n'ai pas trouvé de bien moins cher correspondant à vos autres critères pour le moment. "
            "Les biens présentés précédemment restent les plus abordables.",
            "search",
            quick_replies=["Je veux visiter le premier", "Nouvelle recherche"],
        )
    if not result["results"]:
        n = len(result["alternatives"])
        result["message"] = f"{property_search.NO_EXACT_MESSAGE} Voici {n} bien{'s' if n > 1 else ''} qui s'en rapproche{'nt' if n > 1 else ''}."
    intro = f"J'ai cherché des biens à moins de {property_search._fmt_money(criteria['budget_max'] + 1)}. "
    return _present_search(state, result, intro)


def _handle_select(message, refs, state, user, use_llm):
    ids, error = _resolve(refs, state)
    if error:
        return _result(error, "select")
    cards = _cards_for(ids, state)
    if not cards:
        return _result("Ce bien n'est plus disponible sur DOMIORA. Voulez-vous relancer la recherche ?", "select")
    if len(cards) == 1:
        card = cards[0]
        state["focus_id"] = card["id"]
        number = f"n°{card['index']} " if card.get("index") else ""
        follow = "Compare les deux premiers" if card.get("index") == 1 else "Compare avec le premier"
        return _result(
            f"Voici le bien {number}: {_label(card)}, {card['price']} à {card['city']}. Souhaitez-vous demander une visite ou le comparer ?",
            "select",
            cards=cards,
            actions=[{"label": "Voir le bien", "url": card["url"], "kind": "primary"}],
            quick_replies=["Je veux le visiter", "Comment contacter le propriétaire ?", follow],
        )
    state["selection_ids"] = [c["id"] for c in cards]
    state["focus_id"] = None
    numbers = " et ".join(f"n°{c['index']}" for c in cards if c.get("index"))
    return _result(
        f"Voici les biens {numbers}." if numbers else "Voici les biens sélectionnés.",
        "select",
        cards=cards,
        quick_replies=["Compare-les", "Je préfère le premier"],
    )


def _handle_compare(message, refs, state, user, use_llm):
    from django.urls import reverse

    text = normalize(message)
    if "avec le premier" in text and state["focus_id"] and state["presented_ids"]:
        ids, error = [state["presented_ids"][0], state["focus_id"]], None
    else:
        ids, error = _resolve(refs, state, default_all=True)
    if error:
        return _result(error, "compare")
    if refs["count"] is None and not refs["indexes"] and re.search(r"\bdeux\b", text):
        ids = ids[:2]
    props = _visible_by_ids(list(dict.fromkeys(ids))[:3])
    if len(props) < 2:
        return _result(
            "Il me faut au moins deux biens pour faire une comparaison. Lancez une recherche, puis dites-moi par exemple « compare les deux premiers ».",
            "compare",
        )
    comparison = property_compare.compare(props, use_llm=use_llm)
    presented = state["presented_ids"]
    for item in comparison["properties"]:
        item["index"] = presented.index(item["id"]) + 1 if item["id"] in presented else None
        item.pop("rows", None)
        item.pop("image", None)
    state["selection_ids"] = [p.pk for p in props]
    state["focus_id"] = None
    names = " et ".join(_label(p) for p in props)
    return _result(
        f"Voici la comparaison de {names}.\n{comparison['summary']}",
        "compare",
        comparison=comparison,
        actions=[{
            "label": "Ouvrir le comparateur",
            "url": reverse("properties:compare") + "?ids=" + ",".join(str(p.pk) for p in props),
            "kind": "primary",
        }],
        quick_replies=["Je préfère le premier", "Je préfère le deuxième"],
        source=comparison["source"],
    )


def _single_target(refs, state, purpose):
    ids, error = _resolve(refs, state)
    if error:
        return None, _result(error, purpose)
    if len(ids) != 1:
        if len(state["presented_ids"]) > 1:
            verb = "visiter" if purpose == "visit" else "contacter"
            return None, _result(
                f"Quel bien souhaitez-vous {verb} ? Indiquez son numéro, par exemple « le deuxième ».",
                purpose,
                quick_replies=["Le premier", "Le deuxième"],
            )
        return None, None
    props = _visible_by_ids(ids)
    if not props:
        return None, _result("Ce bien n'est plus disponible sur DOMIORA. Voulez-vous relancer la recherche ?", purpose)
    return props[0], None


def _handle_visit(message, refs, state, user, use_llm):
    prop, early = _single_target(refs, state, "visit")
    if early:
        return early
    if prop is None:
        text, actions = knowledge.faq_answer("visit", user)
        return _result(text, "faq", actions=actions)
    state["focus_id"] = prop.pk
    text, actions = connection_route(user, prop, "visit")
    return _result(text, "visit", cards=_cards_for([prop.pk], state), actions=actions)


def _handle_contact(message, refs, state, user, use_llm):
    privacy = ""
    if _PRIVATE_RE.search(normalize(message)):
        privacy = "Je ne communique jamais les coordonnées privées des propriétaires. "
    prop, early = _single_target(refs, state, "contact")
    if early:
        early["reply"] = privacy + early["reply"]
        return early
    if prop is None:
        text, actions = knowledge.faq_answer("contact", user)
        return _result(text, "faq", actions=actions)
    state["focus_id"] = prop.pk
    text, actions = connection_route(user, prop, "contact")
    return _result(privacy + text, "contact", actions=actions)


def _handle_payment_claim(message, refs, state, user, use_llm):
    from django.urls import reverse

    from messaging.views import _has_paid_for_property
    from properties.models import PropertyUnlock

    base = "Je ne peux pas confirmer un paiement moi-même : c'est FedaPay qui confirme le paiement au système DOMIORA. "
    if not user or not user.is_authenticated:
        return _result(
            base + "Connectez-vous à votre espace client pour retrouver vos mises en relation actives.",
            "payment_claim",
            actions=[{"label": "Se connecter", "url": reverse("accounts:login"), "kind": "primary"}],
        )
    unlocked = {"label": "Biens débloqués", "url": reverse("dashboard:client_unlocked"), "kind": "primary"}
    ids, _ = _resolve(refs, state)
    props = _visible_by_ids(ids[:1])
    if props:
        prop = props[0]
        if _has_paid_for_property(user, prop):
            _, actions = connection_route(user, prop, "contact")
            return _result(
                base + f"Le système indique bien une mise en relation active avec le propriétaire de {_label(prop)}.",
                "payment_claim", actions=actions,
            )
        return _result(
            base + f"Pour l'instant, aucune mise en relation active n'est enregistrée avec le propriétaire de {_label(prop)}. "
            "Si vous venez de payer, la confirmation de FedaPay peut prendre quelques instants ; vérifiez ensuite dans « Biens débloqués ».",
            "payment_claim", actions=[unlocked],
        )
    count = PropertyUnlock.objects.filter(user=user).values("property__owner").distinct().count()
    return _result(
        base + f"Le système enregistre actuellement {count} mise(s) en relation active(s) sur votre compte. "
        "Si un paiement récent n'apparaît pas, la confirmation de FedaPay peut prendre quelques instants.",
        "payment_claim", actions=[unlocked],
    )


_FAQ_QUICK_REPLIES = {
    "payment": ["Pourquoi dois-je payer ?", "Comment demander une visite ?"],
    "contact": ["Comment fonctionne FedaPay ?", "Je cherche un appartement à Lomé"],
    "find_property": ["Un appartement à Lomé, 2 chambres", "Une maison à Lomé avec parking"],
}


def _handle_faq(message, refs, state, user, use_llm, topic):
    answer = knowledge.faq_answer(topic, user)
    if not answer:
        return _handle_general(message, refs, state, user, use_llm)
    text, actions = answer
    return _result(text, "faq", actions=actions, quick_replies=_FAQ_QUICK_REPLIES.get(topic, []))


def _presented_context(state):
    """Données publiques des biens déjà présentés, pour répondre aux questions de suivi."""
    lines = []
    for card in _cards_for(state["presented_ids"], state):
        parts = [
            f"n°{card['index']}" if card.get("index") else "",
            card["title"], card["property_type"], card["transaction"], card["price"], card["city"],
            f"{card['bedrooms']} chambres" if card["bedrooms"] else "chambres non renseignées",
            f"{card['surface']} m²" if card["surface"] else "superficie non renseignée",
        ]
        reasons = "; ".join(r["text"] for r in card.get("reasons", []))
        lines.append(" | ".join(p for p in parts if p) + (f" | {reasons}" if reasons else ""))
    return "\n".join(lines)


def _handle_general(message, refs, state, user, use_llm):
    if use_llm and llm_service.is_configured():
        system = knowledge.SYSTEM_PROMPT
        context = _presented_context(state)
        if context:
            system += "\nBiens actuellement présentés à l'utilisateur (seules données de biens que tu peux citer) :\n" + context
        role = getattr(user, "role", None) if user and user.is_authenticated else "visiteur"
        system += f"\nRôle de l'utilisateur : {role}."
        messages = [{"role": "system", "content": system}]
        for item in state["history"][-8:]:
            messages.append({"role": item["role"], "content": item["content"][:1000]})
        messages.append({"role": "user", "content": message[:2000]})
        text, provider = llm_service.complete(messages, max_tokens=400, temperature=0.4)
        if text:
            return _result(text.strip()[:1500], "general", source=provider.lower())
    return _result(knowledge.GENERIC_HELP, "general", quick_replies=knowledge.DEFAULT_QUICK_REPLIES)


def handle_assistant_message(message, user=None, state=None, use_llm=True):
    """
    Point d'entrée de l'Assistant DOMIORA.
    Retourne (nouvel_état, réponse_sérialisable).
    """
    state = _load_state(state)
    intent, refs, topic = detect_intent(message, state)

    if intent == "reset":
        state = new_assistant_state()
        result = _result("C'est noté, on repart de zéro. Que recherchez-vous ?", "reset", quick_replies=knowledge.DEFAULT_QUICK_REPLIES)
    elif intent == "greeting":
        result = _result(knowledge.GREETING, "greeting", quick_replies=knowledge.DEFAULT_QUICK_REPLIES)
    elif intent == "thanks":
        result = _result("Avec plaisir ! N'hésitez pas si vous avez une autre question.", "thanks")
    elif intent == "bye":
        result = _result("Au revoir, et bonne recherche sur DOMIORA !", "bye")
    elif intent == "faq":
        result = _handle_faq(message, refs, state, user, use_llm, topic)
    elif intent == "search_list":
        result = _handle_search(message, refs, state, user, use_llm, show_now=True, fresh=True)
    else:
        handler = {
            "search": _handle_search,
            "cheaper": _handle_cheaper,
            "select": _handle_select,
            "compare": _handle_compare,
            "visit": _handle_visit,
            "contact": _handle_contact,
            "payment_claim": _handle_payment_claim,
            "general": _handle_general,
        }[intent]
        result = handler(message, refs, state, user, use_llm)

    result["reply"] = _sanitize_payment_provider_names(result["reply"])
    state["history"] = (
        state["history"]
        + [{"role": "user", "content": message[:500]}, {"role": "assistant", "content": result["reply"][:800]}]
    )[-MAX_HISTORY:]
    return state, result
