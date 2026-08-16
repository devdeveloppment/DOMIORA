from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """Restrict a view to users whose .role is in `roles` (superusers always pass)."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            # Allow both CLIENT and BUYER for client dashboard access
            # Allow both OWNER and AGENT for owner dashboard access
            user_role = request.user.role
            if user_role == "buyer":
                user_role = "client"  # Treat buyers as clients for access control
            if user_role == "agent":
                user_role = "owner"  # Treat agents as owners for access control
            if request.user.is_superuser or user_role in roles:
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
