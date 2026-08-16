import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User

# Créer un compte admin si n'existe pas
admin_username = "admin"
admin_email = "admin@domiora.com"
admin_password = "admin123"  # Changez ceci en production!

if not User.objects.filter(username=admin_username).exists():
    admin = User.objects.create_superuser(
        username=admin_username,
        email=admin_email,
        password=admin_password,
        role=User.Role.ADMIN
    )
    print(f"✅ Compte administrateur créé avec succès!")
    print(f"   Nom d'utilisateur: {admin_username}")
    print(f"   Email: {admin_email}")
    print(f"   Mot de passe: {admin_password}")
    print(f"   URL de connexion: http://127.0.0.1:8000/compte/admin-login/")
else:
    print(f"⚠️ Un compte administrateur existe déjà avec le nom d'utilisateur '{admin_username}'")
    admin = User.objects.get(username=admin_username)
    print(f"   Email: {admin.email}")
