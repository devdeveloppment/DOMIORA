# Ce fichier est conservé pour la compatibilité des imports existants.
# L'intégration PayDunya a été supprimée et remplacée par FedaPay.
# Toutes les fonctions ici redirigent vers le module FedaPay.

from .fedapay import (
    generate_fedapay_payment_url as generate_paydunya_payment_url,
    verify_fedapay_payment as verify_paydunya_payment,
    verify_fedapay_webhook_signature as verify_paydunya_signature,
)

__all__ = [
    "generate_paydunya_payment_url",
    "verify_paydunya_payment",
    "verify_paydunya_signature",
]
