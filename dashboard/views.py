from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from accounts.models import User


@login_required
def dashboard_redirect(request):
    user = request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        return redirect("dashboard:admin_overview")
    if user.role == User.Role.AGENT:
        return redirect("dashboard:agent_overview")
    return redirect("dashboard:buyer_overview")
