"""
DOMIORA AI Assistant
====================

Intelligent assistant using the new services/ai_assistant.py module
with complete DOMIORA business context and role-aware responses.
"""
import logging
from django.conf import settings
from properties.models import Property

logger = logging.getLogger(__name__)


def get_assistant_reply(message, conversation_history=None, user=None):
    """
    Main entry point used by the chat widget view.
    
    Uses the new intelligent assistant service from services/ai_assistant.py
    which includes complete DOMIORA business context and role-aware responses.
    
    Args:
        message: User message
        conversation_history: List of previous messages
        user: User object (optional, for role detection)
    
    Returns:
        dict: {
            'reply': str,
            'matches': list of Property objects,
            'source': str
        }
    """
    from services.ai_assistant import get_assistant_response
    
    # Detect user role
    user_role = None
    if user and user.is_authenticated:
        if hasattr(user, 'role'):
            if user.role == 'owner':
                user_role = 'owner'
            elif user.role == 'admin':
                user_role = 'admin'
    else:
        user_role = 'visitor'
    
    # Call the new intelligent assistant service
    result = get_assistant_response(
        message, 
        conversation_history=conversation_history,
        user_role=user_role
    )
    
    # Extract properties from the result
    properties = []
    if result.get('properties'):
        # Convert property dicts back to Property objects for compatibility
        from properties.models import Property
        property_ids = [p.get('id') for p in result['properties'] if p.get('id')]
        if property_ids:
            properties = list(Property.objects.filter(id__in=property_ids))
    
    return {
        'reply': result.get('response'),
        'matches': properties,
        'source': 'gemini_intelligent'
    }
