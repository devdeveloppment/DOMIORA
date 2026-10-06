from accounts.models import User


def user_dash_role(request):
    """Injecte le rôle actif du tableau de bord dans le contexte de chaque template."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    current_path = request.path

    # 1. Détection rapide à partir du préfixe de l'URL, sans accès base de données.
    if current_path.startswith('/dashboard/proprietaire/'):
        return {"dash_role": "owner"}
    elif current_path.startswith('/dashboard/admin-panel/'):
        return {"dash_role": "admin"}
    elif current_path.startswith('/dashboard/client/'):
        return {"dash_role": "client"}

    # 2. Pour les pages globales, on se base sur la session pour garder le bon contexte.
    dash_role = request.session.get('dash_role')
    if not dash_role:
        role = getattr(request.user, "role", User.Role.CLIENT)
        is_superuser = getattr(request.user, "is_superuser", False)
        if role == User.Role.ADMIN or is_superuser:
            dash_role = "admin"
        elif role == User.Role.OWNER:
            dash_role = "owner"
        else:
            dash_role = "client"

    return {"dash_role": dash_role}
