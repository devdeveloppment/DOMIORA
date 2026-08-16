"""
Email Service for DOMIORA
Handles sending emails for identity verification and other notifications
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_identity_verification_email(user, verification_status, rejection_reason=''):
    """
    Send email for identity verification result
    
    Args:
        user: User instance
        verification_status: str - 'approved' or 'rejected'
        rejection_reason: str - reason for rejection (if applicable)
    """
    dashboard_url = f"{settings.BASE_URL}/dashboard/proprietaire/"
    
    if verification_status == 'approved':
        subject = '✅ Votre identité a été validée - DOMIORA'
        template = 'accounts/emails/identity_verified.html'
        context = {
            'user': user,
            'dashboard_url': dashboard_url
        }
    else:
        subject = '❌ Votre identité a été refusée - DOMIORA'
        template = 'accounts/emails/identity_rejected.html'
        context = {
            'user': user,
            'rejection_reason': rejection_reason,
            'dashboard_url': dashboard_url
        }
    
    try:
        html_message = render_to_string(template, context)
        
        send_mail(
            subject=subject,
            message='',  # Plain text version (empty, using HTML only)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Email sent to {user.email} for verification {verification_status}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return False


def send_welcome_email(user):
    """Send welcome email to new users"""
    subject = 'Bienvenue sur DOMIORA !'
    dashboard_url = f"{settings.BASE_URL}/dashboard/"
    
    context = {
        'user': user,
        'dashboard_url': dashboard_url
    }
    
    try:
        html_message = render_to_string('accounts/emails/welcome.html', context)
        
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return False
