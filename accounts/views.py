from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html

from . import throttle
from .forms import RegisterForm, OwnerRegisterForm, ClientPostPaymentForm, ProfileForm
from .models import User


class CustomLoginView(LoginView):
    """Vue de connexion standard avec blocage explicite des comptes admin et limitation des échecs."""
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if throttle.is_locked(request, request.POST.get("username")):
            messages.error(request, throttle.LOCKED_MESSAGE)
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        if self.request.method == "POST" and not form.get_user():
            throttle.register_failure(self.request, self.request.POST.get("username"))
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form.get_user()
        # Block admin users from regular login
        if user.is_superuser or user.role == User.Role.ADMIN:
            messages.error(
                self.request,
                format_html(
                    "Les administrateurs doivent utiliser la page de connexion dédiée. "
                    "<a href=\"{}\" class=\"underline font-bold\">Accéder à la connexion admin</a>",
                    reverse("accounts:admin_login"),
                ),
            )
            return self.form_invalid(form)
        throttle.reset(self.request, self.request.POST.get("username"))

        # Set the appropriate session role based on user role
        if user.role == User.Role.OWNER:
            self.request.session['dash_role'] = 'owner'
        elif user.role == User.Role.CLIENT:
            self.request.session['dash_role'] = 'client'
        self.request.session.modified = True

        return super().form_valid(form)


def client_login(request):
    """Connexion spéciale pour les clients déjà payants et autorisés à entrer dans l'espace client."""
    # Redirect if already logged in as client
    if request.user.is_authenticated and request.user.role == User.Role.CLIENT:
        return redirect("dashboard:client_overview")
    
    # If logged in as non-client, show error but don't redirect (avoid 405 error)
    if request.user.is_authenticated:
        user_name = request.user.get_full_name() or request.user.username
        messages.warning(request, f"Vous êtes déjà connecté en tant que {user_name}. Pour accéder à l'espace client, vous devez d'abord vous déconnecter.")
        # Still render the page with the warning message
        return render(request, "accounts/client_login.html")
    
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password")

        if not (email and password):
            messages.error(request, "Veuillez remplir tous les champs.")
        elif throttle.is_locked(request, email):
            messages.error(request, throttle.LOCKED_MESSAGE)
        else:
            # Message identique que l'e-mail existe ou non : aucune fuite sur les comptes enregistrés.
            authenticated_user = None
            for candidate in User.objects.filter(email__iexact=email)[:5]:
                authenticated_user = authenticate(request, username=candidate.username, password=password)
                if authenticated_user is not None:
                    break
            if authenticated_user is None:
                throttle.register_failure(request, email)
                messages.error(request, "E-mail ou mot de passe incorrect.")
            elif authenticated_user.role != User.Role.CLIENT:
                messages.error(request, "Ce compte n'est pas un compte client. Utilisez la page de connexion appropriée.")
            else:
                throttle.reset(request, email)
                login(request, authenticated_user)
                request.session['dash_role'] = 'client'
                request.session.modified = True
                messages.success(request, f"Bienvenue {authenticated_user.get_full_name() or authenticated_user.username} !")
                return redirect("dashboard:client_overview")

    return render(request, "accounts/client_login.html")


# ─────────────────────────────────────────────────────────────────────────────
# Legacy register view (kept for admin use / direct URL access)
# ─────────────────────────────────────────────────────────────────────────────
def register(request):
    """Route historique : redirige vers la bonne page d'inscription selon le parcours."""
    return redirect("accounts:publish_landing")


# ─────────────────────────────────────────────────────────────────────────────
# Landing page: "Publier un bien"
# ─────────────────────────────────────────────────────────────────────────────
def publish_landing(request):
    """Page intermédiaire pour le bouton de publication d'un bien."""
    return render(request, "accounts/publish_landing.html")


# ─────────────────────────────────────────────────────────────────────────────
# Owner-only registration
# ─────────────────────────────────────────────────────────────────────────────
def register_owner(request):
    """Inscription réservée aux propriétaires immobiliers."""
    if request.user.is_authenticated:
        user_name = request.user.get_full_name() or request.user.username
        messages.warning(request, f"Vous êtes déjà connecté en tant que {user_name}. Si vous souhaitez créer un nouveau compte, veuillez vous déconnecter d'abord.")

    if request.method == "POST":
        form = OwnerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            _notify_admins_new_owner(user)
            _send_welcome_email(user)

            # Connexion immédiate : le propriétaire arrive directement sur la vérification d'identité,
            # étape obligatoire avant toute publication.
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session["dash_role"] = "owner"
            messages.success(
                request,
                f"Bienvenue {user.first_name} ! Votre compte propriétaire est créé. "
                "Dernière étape avant de publier : envoyez votre pièce d'identité."
            )
            return redirect("dashboard:owner_verify_identity")
    else:
        form = OwnerRegisterForm()
    return render(request, "accounts/register_owner.html", {"form": form})



# ─────────────────────────────────────────────────────────────────────────────
# Ancienne inscription « après paiement »
# ─────────────────────────────────────────────────────────────────────────────
def register_client_post_payment(request, slug):
    """
    Route historique. Elle créait une relation sans aucune preuve de paiement ;
    elle renvoie désormais vers le parcours de paiement sécurisé (création du compte
    puis paiement vérifié côté serveur).
    """
    return redirect("properties:payment_redirect", slug=slug)


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def profile(request):
    """Permet à l'utilisateur de modifier son profil et ses informations de contact."""
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form, "active": "profile"})


# ─────────────────────────────────────────────────────────────────────────────
# Public Profile
# ─────────────────────────────────────────────────────────────────────────────
def public_profile(request, username):
    """Affiche le profil public d'un propriétaire avec ses biens publiés."""
    owner = get_object_or_404(User, username=username, role=User.Role.OWNER)
    
    # Get owner's published properties
    properties = owner.properties.filter(is_published=True, is_validated=True).select_related('owner').prefetch_related('images')
    
    context = {
        "owner": owner,
        "properties": properties,
        "published_count": owner.properties_count,
        "active_count": owner.active_properties_count,
        "total_views": owner.get_total_views_count(),
        "total_favorites": owner.get_total_favorites_count(),
        "verified_count": owner.verified_properties_count,
        "pending_count": owner.pending_properties_count,
        "rejected_count": owner.rejected_properties_count,
        "response_rate": owner.response_rate,
        "average_response_display": owner.average_response_display,
    }
    return render(request, "accounts/public_profile.html", context)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _notify_admins_new_owner(user):
    if user.role != User.Role.OWNER:
        return
    try:
        from notifications.models import Notification
        admins = User.objects.filter(role=User.Role.ADMIN)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title="Nouveau propriétaire inscrit",
                message=f"Le propriétaire {user.get_full_name() or user.username} vient de s'inscrire.",
                notification_type="systeme",
                link="/dashboard/admin-panel/utilisateurs/",
            )
    except Exception:
        pass


def _send_welcome_email(user):
    try:
        from django.core.mail import send_mail
        send_mail(
            subject="Bienvenue sur DOMIORA",
            message=f"Bonjour {user.first_name},\n\nVotre compte DOMIORA a bien été créé.\n\nL'équipe DOMIORA",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email] if user.email else [],
            fail_silently=True,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Admin-only login (separate from user authentication)
# ─────────────────────────────────────────────────────────────────────────────
def admin_login(request):
    """Page de connexion dédiée aux administrateurs du système."""
    # Redirect if already logged in as admin
    if request.user.is_authenticated and (request.user.is_superuser or request.user.role == User.Role.ADMIN):
        return redirect("dashboard:admin_overview")
    
    # Redirect if logged in as non-admin (force logout first)
    if request.user.is_authenticated:
        messages.warning(request, "Vous devez vous déconnecter de votre compte utilisateur pour accéder à l'admin.")
        return redirect("accounts:logout")
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        if username and password and throttle.is_locked(request, username):
            messages.error(request, throttle.LOCKED_MESSAGE)
        elif username and password:
            user = authenticate(request, username=username, password=password)
            if user is None:
                throttle.register_failure(request, username)

            if user is not None:
                # Check if user is admin
                if user.is_superuser or user.role == User.Role.ADMIN:
                    throttle.reset(request, username)
                    login(request, user)
                    # Set admin session role
                    request.session['dash_role'] = 'admin'
                    request.session.modified = True
                    messages.success(request, f"Bienvenue {user.get_full_name() or user.username}, vous êtes connecté en tant qu'administrateur.")
                    return redirect("dashboard:admin_overview")
                else:
                    messages.error(request, "Ce compte n'a pas les droits administrateur. Utilisez la page de connexion utilisateur.")
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
        else:
            messages.error(request, "Veuillez remplir tous les champs.")
    
    return render(request, "accounts/admin_login.html")

def custom_logout(request):
    """Déconnexion personnalisée pour éviter les problèmes de rotation CSRF sur les requêtes."""
    from django.contrib.auth import logout
    logout(request)
    return redirect("core:home")
