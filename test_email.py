import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("=== DEBUT DU TEST D'ENVOI D'EMAIL ===")
print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
print(f"EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'NON DEFINI'}")
print(f"ADMIN_NOTIFICATION_EMAIL: {settings.ADMIN_NOTIFICATION_EMAIL}")
print("-----------------------------------")

try:
    result = send_mail(
        subject="[Test] Vérification de la configuration d'email",
        message="Bonjour, voici un test pour vérifier que les emails fonctionnent correctement.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
        fail_silently=False,
    )
    if result:
        print("\n✅ SUCCÈS : L'email a été envoyé correctement à " + settings.ADMIN_NOTIFICATION_EMAIL)
    else:
        print("\n❌ ÉCHEC : La fonction a retourné 0 (aucun email envoyé) mais sans erreur.")
except Exception as e:
    print("\n❌ ERREUR LORS DE L'ENVOI :")
    print(str(e))
    print("\n--- Trace complète ---")
    traceback.print_exc()
