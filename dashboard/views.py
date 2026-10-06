from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from accounts.models import User


def dashboard_admission(request):
    """Page d'admission pour l'accès réservé aux administrateurs."""
    # Si l'utilisateur connecté est déjà administrateur, il est dirigé directement vers le dashboard admin.
    if request.user.is_authenticated and (request.user.is_superuser or request.user.role == User.Role.ADMIN):
        return redirect("dashboard:admin_overview")

    # Traitement du formulaire de connexion admin.
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        # Vérifie que le compte est bien administrateur avant d'autoriser l'accès.
        if user is not None and (user.is_superuser or user.role == User.Role.ADMIN):
            login(request, user)
            request.session['dash_role'] = 'admin'
            request.session.modified = True
            return redirect("dashboard:admin_overview")
        else:
            return render(request, "dashboard/admin_admission.html", {
                'error': "Identifiants administrateur invalides"
            })

    return render(request, "dashboard/admin_admission.html")


@login_required
def dashboard_redirect(request):
    """Redirige l'utilisateur vers le bon tableau de bord selon son rôle."""
    user = request.user

    # Les administrateurs accèdent au tableau de bord d'administration.
    if user.is_superuser or user.role == User.Role.ADMIN:
        request.session['dash_role'] = 'admin'
        request.session.modified = True
        return redirect("dashboard:admin_overview")

    # Les propriétaires sont envoyés vers leur espace dédié.
    if user.role == User.Role.OWNER:
        request.session['dash_role'] = 'owner'
        request.session.modified = True
        return redirect("dashboard:owner_overview")

    # Par défaut, les autres utilisateurs connectés vont vers le dashboard client.
    request.session['dash_role'] = 'client'
    request.session.modified = True
    return redirect("dashboard:client_overview")

