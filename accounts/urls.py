from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "accounts"

urlpatterns = [
    # ── Legacy & Owner registration ──────────────────────────────────────────
    path("inscription/", views.register, name="register"),
    path("inscription/proprietaire/", views.register_owner, name="register_owner"),
    path("publier-un-bien/", views.publish_landing, name="publish_landing"),

    # ── Client post-payment registration ────────────────────────────────────
    path("inscription/client/<slug:slug>/", views.register_client_post_payment, name="register_client_post_payment"),

    # ── Auth ─────────────────────────────────────────────────────────────────
    path("connexion/", views.CustomLoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin-login/", views.admin_login, name="admin_login"),  # Admin-only login
    path("mon-espace/", views.client_login, name="client_login"),  # Client-only login
    path("profil/", views.profile, name="profile"),
    path("u/<str:username>/", views.public_profile, name="public_profile"),

    # ── Password reset ────────────────────────────────────────────────────────
    path(
        "mot-de-passe-oublie/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/emails/password_reset_email.txt",
            subject_template_name="accounts/emails/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe-oublie/envoye/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reinitialiser/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "reinitialiser/termine/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
