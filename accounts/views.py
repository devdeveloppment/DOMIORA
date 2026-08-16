from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.conf import settings

from .forms import RegisterForm, OwnerRegisterForm, ClientPostPaymentForm, ProfileForm
from .models import User


class CustomLoginView(LoginView):
    """Custom login view that blocks admin access."""
    template_name = "accounts/login.html"
    
    def form_valid(self, form):
        user = form.get_user()
        # Block admin users from regular login
        if user.is_superuser or user.role == User.Role.ADMIN:
            messages.error(
                self.request,
                "Les administrateurs doivent utiliser la page de connexion dédiée. "
                "<a href='/accounts/admin-login/' class='underline font-bold'>Accéder à la connexion admin</a>"
            )
            return self.form_invalid(form)
        return super().form_valid(form)


def client_login(request):
    """
    Simple client login page for existing clients who have already paid.
    Allows login with email or phone + password.
    """
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
        email = request.POST.get("email")  # email only
        password = request.POST.get("password")
        
        if email and password:
            # Try to find user by email
            user = None
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
            
            if user:
                # Authenticate user
                authenticated_user = authenticate(request, username=user.username, password=password)
                
                if authenticated_user is not None:
                    # Check if user is client
                    if authenticated_user.role == User.Role.CLIENT:
                        login(request, authenticated_user)
                        # Set client session role
                        request.session['dash_role'] = 'client'
                        request.session.modified = True
                        messages.success(request, f"Bienvenue {authenticated_user.get_full_name() or authenticated_user.username} !")
                        return redirect("dashboard:client_overview")
                    else:
                        messages.error(request, "Ce compte n'est pas un compte client. Utilisez la page de connexion appropriée.")
                else:
                    messages.error(request, "Mot de passe incorrect.")
            else:
                messages.error(request, "Aucun compte trouvé avec cet email.")
        else:
            messages.error(request, "Veuillez remplir tous les champs.")
    
    return render(request, "accounts/client_login.html")


# ─────────────────────────────────────────────────────────────────────────────
# Legacy register view (kept for admin use / direct URL access)
# ─────────────────────────────────────────────────────────────────────────────
def register(request):
    """Legacy route — redirect everyone to the appropriate registration page."""
    return redirect("accounts:publish_landing")


# ─────────────────────────────────────────────────────────────────────────────
# Landing page: "Publier un bien"
# ─────────────────────────────────────────────────────────────────────────────
def publish_landing(request):
    """Intermediate page for the 'Publier un bien' button."""
    if request.user.is_authenticated and request.user.role == User.Role.OWNER:
        return redirect("dashboard:owner_property_create")
    return render(request, "accounts/publish_landing.html")


# ─────────────────────────────────────────────────────────────────────────────
# Owner-only registration
# ─────────────────────────────────────────────────────────────────────────────
def register_owner(request):
    """
    Registration page exclusively for property owners.
    Flow:
      1. User fills the form
      2. Account is created (NOT auto-logged in)
      3. User is redirected to the login page → lands on owner dashboard
    
    Note: The form is shown even if an admin is browsing the site,
    so testing the flow works without having to log out first.
    """
    # Only skip the form if already logged in AS an owner
    if request.user.is_authenticated and request.user.role == User.Role.OWNER:
        return redirect("dashboard:owner_overview")

    if request.method == "POST":
        form = OwnerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            _notify_admins_new_owner(user)
            _send_welcome_email(user)

            messages.success(
                request,
                f"Bienvenue {user.first_name} ! Votre compte propriétaire a été créé. "
                "Connectez-vous maintenant pour accéder à votre tableau de bord."
            )
            # Redirect to login — "next" sends them directly to owner dashboard
            from django.urls import reverse
            login_url = reverse("accounts:login")
            return redirect(f"{login_url}?next=/dashboard/proprietaire/")
    else:
        form = OwnerRegisterForm()
    return render(request, "accounts/register_owner.html", {"form": form})



# ─────────────────────────────────────────────────────────────────────────────
# Client registration AFTER payment (auto-unlock + auto-login)
# ─────────────────────────────────────────────────────────────────────────────
def register_client_post_payment(request, slug):
    """
    Called after successful Maketou payment.
    Creates a client account, logs them in automatically, creates the PropertyUnlock,
    then redirects to the payment confirmation page with full contact details.
    """
    from properties.models import Property, PropertyUnlock

    property_obj = None
    try:
        property_obj = Property.objects.select_related("owner").get(slug=slug)
    except Property.DoesNotExist:
        pass

    # If already logged in, just create the unlock and show confirmation
    if request.user.is_authenticated:
        if property_obj:
            PropertyUnlock.objects.get_or_create(user=request.user, property=property_obj)
        return redirect("properties:payment_confirmation", slug=slug)

    if request.method == "POST":
        form = ClientPostPaymentForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Auto-unlock the property for this new client
            if property_obj:
                PropertyUnlock.objects.get_or_create(user=user, property=property_obj)
                # Notify owner
                if property_obj.owner:
                    from notifications.models import Notification
                    Notification.objects.create(
                        user=property_obj.owner,
                        title="🔓 Nouvelle mise en relation",
                        message=f"{user.get_full_name() or user.username} a payé les frais de mise en relation pour « {property_obj.title} ».",
                        notification_type="systeme",
                        link="/messagerie/",
                    )

            # Auto-login the new client
            login(request, user)

            # Force session role to 'client'
            request.session['dash_role'] = 'client'
            request.session.modified = True

            messages.success(
                request,
                f"Bienvenue {user.first_name} ! Votre compte a été créé et les coordonnées du propriétaire sont maintenant accessibles."
            )
            return redirect("properties:payment_confirmation", slug=slug)
    else:
        form = ClientPostPaymentForm()

    return render(request, "accounts/register_client_post_payment.html", {
        "form": form,
        "property_slug": slug,
        "property": property_obj,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def profile(request):
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
    """Public profile page for property owners"""
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
    """
    Dedicated admin login page.
    Accessible only via specific URL /admin-login/
    Only allows admin accounts to log in.
    """
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
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # Check if user is admin
                if user.is_superuser or user.role == User.Role.ADMIN:
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
