from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()

def role_required(*roles):
    """
    Restrict a view to users whose .role is in `roles` (superusers always pass).
    Also accepts users who have the correct dash_role in their session, to support
    test accounts navigating across roles (e.g. an owner account browsing as client).
    """

    # Map Django role choices to their session string equivalents
    _role_to_dash = {
        "client": "client",
        "owner": "owner",
        "admin": "admin",
    }

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            # 1. Superuser always passes
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            # 2. User has a role that matches one of the required roles
            if request.user.role in roles:
                return view_func(request, *args, **kwargs)
            # 3. Session dash_role matches one of the required roles
            #    (allows cross-role test accounts to navigate correctly)
            session_dash_role = request.session.get("dash_role", "")
            for role in roles:
                if _role_to_dash.get(role, role) == session_dash_role:
                    return view_func(request, *args, **kwargs)
            # 4. Special case: allow CLIENT role access for users who have paid
            if User.Role.CLIENT in roles:
                from properties.models import PropertyUnlock
                has_paid = PropertyUnlock.objects.filter(user=request.user).exists()
                if has_paid:
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
