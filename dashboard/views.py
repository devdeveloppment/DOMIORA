from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from accounts.models import User


@login_required
def dashboard_redirect(request):
    user = request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        request.session['dash_role'] = 'admin'
        request.session.modified = True
        return redirect("dashboard:admin_overview")
    if user.role == User.Role.OWNER or user.role == User.Role.AGENT:
        request.session['dash_role'] = 'owner'
        request.session.modified = True
        return redirect("dashboard:owner_overview")
    # Default: client
    request.session['dash_role'] = 'client'
    request.session.modified = True
    return redirect("dashboard:client_overview")

