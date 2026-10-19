from django.conf import settings


def payment_settings(request):
    """Expose le tarif de mise en relation et le mode de paiement aux templates."""
    return {
        "contact_fee_amount": settings.CONTACT_FEE_AMOUNT,
        "contact_fee_currency_label": "FCFA",
        "payment_simulation_mode": settings.PAYMENT_MODE == "simulation",
    }
