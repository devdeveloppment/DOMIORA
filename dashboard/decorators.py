from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()

def role_required(*roles):
    """
    Restreint une vue aux utilisateurs dont le rôle réel (`user.role`) figure dans `roles`
    (les superutilisateurs passent toujours).

    Le rôle d'affichage stocké en session (`dash_role`) et l'existence d'un paiement
    n'accordent AUCUN droit : ils servaient auparavant de raccourci et permettaient
    d'accéder à un espace qui n'était pas celui du rôle de l'utilisateur.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "Vous n'avez pas accès à cette page.")
            return redirect("dashboard:redirect")
        return _wrapped
    return decorator


def login_required_custom(view_func):
    """Custom login_required that uses the correct login URL."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        return view_func(request, *args, **kwargs)
    return _wrapped
