import requests
import uuid
import hmac
import hashlib
import json
import logging
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def verify_cinetpay_signature(payload_json, signature, secret_key):
    """
    Verify CinetPay webhook signature using HMAC-SHA256.
    
    Args:
        payload_json: Raw JSON string from webhook
        signature: Signature from x-signature header
        secret_key: CinetPay secret key
        
    Returns:
        bool: True if signature is valid
    """
    try:
        # Create HMAC-SHA256 of the payload
        computed_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare with provided signature (constant time comparison for security)
        return hmac.compare_digest(computed_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def generate_cinetpay_payment_url(request, property_slug, amount=500, customer_name="", customer_email="", customer_phone=""):
    """
    Calls CinetPay API to generate a payment link.
    
    Args:
        request: Django request object
        property_slug: Property identifier
        amount: Amount in FCFA
        customer_name: Customer name
        customer_email: Customer email
        customer_phone: Customer phone number
        
    Returns:
        tuple: (payment_url, transaction_id) or (None, None) if error
    """
    api_key = getattr(settings, 'CINETPAY_API_KEY', '')
    site_id = getattr(settings, 'CINETPAY_SITE_ID', '')
    
    # Validate credentials are configured
    if not api_key or not site_id:
        logger.error("CinetPay credentials not configured in environment")
        return None, None
    
    transaction_id = str(uuid.uuid4())
    
    # URL de retour après paiement
    return_url = request.build_absolute_uri(reverse('properties:payment_confirmation', args=[property_slug]))
    
    # URL de notification (webhook en arrière-plan)
    notify_url = request.build_absolute_uri(reverse('properties:payment_notify', args=[property_slug]))

    payload = {
        "apikey": api_key,
        "site_id": site_id,
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": "XOF",
        "description": f"Frais de mise en relation pour le bien {property_slug}",
        "notify_url": notify_url,
        "return_url": return_url,
        "channels": "ALL",
        "customer_name": customer_name or "Client",
        "customer_surname": "DOMIORA",
        "customer_email": customer_email or "client@domiora.com",
        "customer_phone_number": customer_phone or "00000000",
        "customer_address": "Lome",
        "customer_city": "Lome",
        "customer_country": "TG",
        "customer_state": "TG",
        "customer_zip_code": "00000"
    }

    try:
        response = requests.post(
            "https://api-checkout.cinetpay.com/v2/payment",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") == "201":
            logger.info(f"Payment URL generated for transaction {transaction_id}")
            return data["data"]["payment_url"], transaction_id
        else:
            error_msg = data.get("description", "Unknown error")
            logger.warning(f"CinetPay API returned error: {data.get('code')} - {error_msg}")
            return None, None
    except requests.exceptions.Timeout:
        logger.error("CinetPay API request timed out")
        return None, None
    except requests.exceptions.RequestException as e:
        logger.error(f"CinetPay API request failed: {str(e)}")
        return None, None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"CinetPay API response parsing error: {str(e)}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error during payment URL generation: {str(e)}")
        return None, None


def verify_cinetpay_payment(transaction_id):
    """
    Checks the status of a payment via CinetPay API.
    
    Args:
        transaction_id: Transaction ID to verify
        
    Returns:
        tuple: (success, data) where success is bool
    """
    api_key = getattr(settings, 'CINETPAY_API_KEY', '')
    site_id = getattr(settings, 'CINETPAY_SITE_ID', '')
    
    if not api_key or not site_id:
        logger.error("CinetPay credentials not configured in environment")
        return False, None

    payload = {
        "apikey": api_key,
        "site_id": site_id,
        "transaction_id": transaction_id
    }

    try:
        response = requests.post(
            "https://api-checkout.cinetpay.com/v2/payment/check",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") == "00":
            logger.info(f"Payment verified for transaction {transaction_id}")
            return True, data
        else:
            logger.warning(f"CinetPay payment check returned: {data.get('code')}")
            return False, data
    except requests.exceptions.Timeout:
        logger.error(f"CinetPay payment check timed out for transaction {transaction_id}")
        return False, None
    except requests.exceptions.RequestException as e:
        logger.error(f"CinetPay payment check request failed: {str(e)}")
        return False, None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"CinetPay payment check response parsing error: {str(e)}")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error during payment verification: {str(e)}")
        return False, None
