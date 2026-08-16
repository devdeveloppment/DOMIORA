"""
n8n Service for DOMIORA
Handles communication with n8n webhooks for identity verification workflow
"""
import os
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_identity_verification(verification_request):
    """
    Send identity verification data to n8n webhook
    
    Args:
        verification_request: IdentityVerificationRequest instance
        
    Returns:
        dict: Response from n8n or error information
    """
    webhook_url = os.environ.get('N8N_IDENTITY_VERIFICATION_WEBHOOK', 
                                'https://deniscodeur.app.n8n.cloud/webhook/domiora-identity-verification')
    
    # Get Cloudinary URLs for documents
    id_card_front_url = verification_request.id_document_front.url if verification_request.id_document_front else ""
    id_card_back_url = verification_request.id_document_back.url if verification_request.id_document_back else ""
    
    # Prepare payload
    payload = {
        "owner_id": str(verification_request.owner.id),
        "first_name": verification_request.owner.first_name,
        "last_name": verification_request.owner.last_name,
        "email": verification_request.owner.email,
        "phone": verification_request.owner.phone or "",
        "id_card_front": id_card_front_url,
        "id_card_back": id_card_back_url,
        "id_document_type": verification_request.id_document_type or "",
        "id_document_number": verification_request.id_document_number or "",
        "verification_request_id": str(verification_request.id),
        "resume_url": f"{settings.BASE_URL}/api/verification/resume/{verification_request.id}/"
    }
    
    try:
        logger.info(f"Sending identity verification to n8n: {webhook_url}")
        logger.info(f"Payload: {payload}")
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        response.raise_for_status()
        
        # Update verification request with n8n response data
        response_data = response.json()
        verification_request.n8n_execution_id = response_data.get('execution_id', '')
        verification_request.n8n_resume_url = response_data.get('resume_url', '')
        verification_request.save(update_fields=['n8n_execution_id', 'n8n_resume_url'])
        
        logger.info(f"n8n response: {response_data}")
        
        return {
            'success': True,
            'execution_id': verification_request.n8n_execution_id,
            'resume_url': verification_request.n8n_resume_url
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending to n8n: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def send_admin_notification(verification_request, notification_type):
    """
    Send notification to admin about verification request
    
    Args:
        verification_request: IdentityVerificationRequest instance
        notification_type: str - 'new', 'approved', 'rejected'
        
    Returns:
        dict: Response from n8n or error information
    """
    webhook_url = os.environ.get('N8N_ADMIN_NOTIFICATION_WEBHOOK', '')
    
    if not webhook_url:
        logger.warning("N8N_ADMIN_NOTIFICATION_WEBHOOK not configured")
        return {'success': False, 'error': 'Webhook not configured'}
    
    payload = {
        "notification_type": notification_type,
        "verification_request_id": str(verification_request.id),
        "owner_id": str(verification_request.owner.id),
        "owner_name": verification_request.owner.get_full_name() or verification_request.owner.username,
        "owner_email": verification_request.owner.email,
        "status": verification_request.status,
        "submitted_at": verification_request.submitted_at.isoformat(),
        "admin_url": f"{settings.BASE_URL}/dashboard/admin-panel/verifications-identite/"
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        response.raise_for_status()
        
        return {'success': True, 'data': response.json()}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending admin notification: {str(e)}")
        return {'success': False, 'error': str(e)}
