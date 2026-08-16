import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User

# Vérifier si un compte admin existe
admin_users = User.objects.filter(role=User.Role.ADMIN)

if admin_users.exists():
    print(f"✅ {admin_users.count()} compte(s) administrateur(s) trouvé(s):")
    for admin in admin_users:
        print(f"   - Nom d'utilisateur: {admin.username}")
        print(f"     Email: {admin.email}")
        print(f"     Est superuser: {admin.is_superuser}")
else:
    print("❌ Aucun compte administrateur trouvé.")
    print("Vous pouvez en créer un via le formulaire d'inscription ou en utilisant createsuperuser.")
