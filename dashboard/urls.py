from django.urls import path
from field_verification import views as fv
from moderation import views as moderation_views
from owner_subscriptions import views as subscription_views
from core import views_private

from . import views, views_client, views_owner, views_admin

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_admission, name="admission"),
    path("redirect/", views.dashboard_redirect, name="redirect"),

    # Client
    path("client/", views_client.client_overview, name="client_overview"),
    path("client/favoris/", views_client.client_favorites, name="client_favorites"),
    path("client/demandes/", views_client.client_requests, name="client_requests"),
    path("client/notifications/", views_client.client_notifications, name="client_notifications"),
    path("client/mes-mises-en-relation/", views_client.client_unlocked_properties, name="client_unlocked"),
    path("client/historique/", views_client.client_history, name="client_history"),
    path("client/parametres/", views_client.client_settings, name="client_settings"),
    path("client/messagerie/", views_client.client_messaging, name="client_messaging"),
    path("client/messagerie/<int:pk>/", views_client.client_conversation_detail, name="client_conversation_detail"),

    # Owner (also used by agents)
    path("proprietaire/", views_owner.owner_overview, name="owner_overview"),
    path("proprietaire/biens/", views_owner.owner_properties, name="owner_properties"),
    path("proprietaire/biens/ajouter/", views_owner.owner_property_create, name="owner_property_create"),
    path("proprietaire/biens/en-attente/", views_owner.owner_pending_properties, name="owner_pending_properties"),
    path("proprietaire/biens/validees/", views_owner.owner_published_properties, name="owner_published_properties"),
    path("proprietaire/biens/<int:pk>/modifier/", views_owner.owner_property_edit, name="owner_property_edit"),
    path("proprietaire/biens/<int:pk>/supprimer/", views_owner.owner_property_delete, name="owner_property_delete"),
    path("proprietaire/biens/<int:pk>/publier/", views_owner.owner_property_toggle_publish, name="owner_property_toggle_publish"),
    path("proprietaire/biens/<int:pk>/images/<int:image_id>/supprimer/", views_owner.owner_property_image_delete, name="owner_property_image_delete"),
    path("proprietaire/biens/<int:pk>/images/<int:image_id>/deplacer/", views_owner.owner_property_image_move, name="owner_property_image_move"),
    path("proprietaire/biens/<int:pk>/visite-virtuelle/generer/", views_owner.owner_property_video_generate, name="owner_property_video_generate"),
    path("proprietaire/biens/<int:pk>/visite-virtuelle/statut/", views_owner.owner_property_video_status, name="owner_property_video_status"),
    # REMOVED: owner_requests and owner_request_update_status - visit requests not shown to owners
    path("proprietaire/statistiques/", views_owner.owner_stats, name="owner_stats"),
    path("proprietaire/verification-identite/", views_owner.owner_verify_identity, name="owner_verify_identity"),
    path("proprietaire/profil/", views_owner.owner_profile, name="owner_profile"),
    path("proprietaire/parametres/", views_owner.owner_settings, name="owner_settings"),
    path("proprietaire/notifications/", views_owner.owner_notifications, name="owner_notifications"),
    path("proprietaire/messagerie/", views_owner.owner_messaging, name="owner_messaging"),
    path("proprietaire/messagerie/<int:pk>/", views_owner.owner_conversation_detail, name="owner_conversation_detail"),

    # Admin
    path("admin-panel/", views_admin.admin_overview, name="admin_overview"),
    path("admin-panel/proprietaires/", views_admin.admin_owners, name="admin_owners"),
    path("admin-panel/utilisateurs/", views_admin.admin_users, name="admin_users"),
    path("admin-panel/utilisateurs/<int:pk>/toggle/", views_admin.admin_user_toggle, name="admin_user_toggle"),
    path("admin-panel/utilisateurs/<int:pk>/supprimer/", views_admin.admin_user_delete, name="admin_user_delete"),
    path("admin-panel/proprietes/", views_admin.admin_properties, name="admin_properties"),
    path("admin-panel/proprietes/ajouter/", views_admin.admin_property_create, name="admin_property_create"),
    path("admin-panel/proprietes/<int:pk>/modifier/", views_admin.admin_property_edit, name="admin_property_edit"),
    path("admin-panel/proprietes/<int:pk>/valider/", views_admin.admin_property_validate, name="admin_property_validate"),
    path("admin-panel/proprietes/<int:pk>/visite-virtuelle/generer/", views_admin.admin_property_video_generate, name="admin_property_video_generate"),
    path("admin-panel/proprietes/<int:pk>/rejeter/", views_admin.admin_property_reject, name="admin_property_reject"),
    path("admin-panel/proprietes/<int:pk>/supprimer/", views_admin.admin_property_delete, name="admin_property_delete"),
    path("admin-panel/transactions/", views_admin.admin_transactions, name="admin_transactions"),
    path("admin-panel/finances/", views_admin.admin_finances, name="admin_finances"),
    path("admin-panel/verifications/", views_admin.admin_verifications, name="admin_verifications"),
    path("admin-panel/verifications/<int:pk>/", views_admin.admin_verification_update, name="admin_verification_update"),
    path("admin-panel/verifications-identite/", views_admin.admin_identity_verifications, name="admin_identity_verifications"),
    path("admin-panel/verifications-identite/<int:pk>/", views_admin.admin_identity_verification_detail, name="admin_identity_verification_detail"),
    path("admin-panel/verifications-identite/<int:pk>/action/", views_admin.admin_identity_verification_action, name="admin_identity_verification_action"),
    path("admin-panel/statistiques/", views_admin.admin_stats, name="admin_stats"),
    path("admin-panel/rapports/", views_admin.admin_reports, name="admin_reports"),
    path("admin-panel/parametres/", views_admin.admin_settings, name="admin_settings"),

    # Missions de vérification terrain (admin : décision finale ; vérificateur : contrôle et rapport)
    path("admin-panel/missions/", fv.admin_missions, name="admin_missions"),
    path("admin-panel/missions/nouvelle/", fv.admin_mission_create, name="admin_mission_create"),
    path("admin-panel/missions/<int:pk>/", fv.admin_mission_detail, name="admin_mission_detail"),
    path("admin-panel/verificateurs/ajouter/", fv.admin_verifier_create, name="admin_verifier_create"),
    path("verificateur/", fv.verifier_home, name="verifier_home"),
    path("verificateur/missions/<int:pk>/", fv.verifier_mission, name="verifier_mission"),
    path("verificateur/missions/<int:pk>/preuves/", fv.verifier_evidence_upload, name="verifier_evidence_upload"),
    path("preuves/<int:pk>/", fv.evidence_file, name="mission_evidence_file"),

    # Abonnements propriétaires / agents (paiements simulés)
    path("proprietaire/abonnement/", subscription_views.subscription_home, name="owner_subscription"),
    path("proprietaire/abonnement/action/", subscription_views.subscription_action, name="owner_subscription_action"),
    path("proprietaire/abonnement/paiement/<uuid:reference>/", subscription_views.subscription_payment, name="owner_subscription_payment"),

    # Fichiers sensibles servis après contrôle d'accès
    path("fichiers/identite/<int:pk>/<str:side>/", views_private.identity_document, name="private_identity_document"),
    path("fichiers/identite-profil/<int:pk>/", views_private.user_identity_document, name="private_user_identity_document"),
    path("fichiers/document-bien/<int:pk>/", views_private.property_document, name="private_property_document"),

    # Signalements d'annonces
    path("admin-panel/signalements/", moderation_views.admin_reports, name="admin_listing_reports"),
    path("admin-panel/signalements/<int:pk>/", moderation_views.admin_report_detail, name="admin_listing_report"),
]
