from django.urls import path
from . import views, views_buyer, views_agent, views_admin

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_redirect, name="redirect"),

    # Buyer
    path("acheteur/", views_buyer.buyer_overview, name="buyer_overview"),
    path("acheteur/favoris/", views_buyer.buyer_favorites, name="buyer_favorites"),
    path("acheteur/demandes/", views_buyer.buyer_requests, name="buyer_requests"),

    # Agent
    path("agent/", views_agent.agent_overview, name="agent_overview"),
    path("agent/biens/", views_agent.agent_properties, name="agent_properties"),
    path("agent/biens/ajouter/", views_agent.agent_property_create, name="agent_property_create"),
    path("agent/biens/<int:pk>/modifier/", views_agent.agent_property_edit, name="agent_property_edit"),
    path("agent/biens/<int:pk>/supprimer/", views_agent.agent_property_delete, name="agent_property_delete"),
    path("agent/biens/<int:pk>/publier/", views_agent.agent_property_toggle_publish, name="agent_property_toggle_publish"),
    path("agent/biens/<int:pk>/images/<int:image_id>/supprimer/", views_agent.agent_property_image_delete, name="agent_property_image_delete"),
    path("agent/demandes/", views_agent.agent_requests, name="agent_requests"),
    path("agent/demandes/<int:pk>/<str:status>/", views_agent.agent_request_update_status, name="agent_request_update_status"),
    path("agent/transactions/", views_agent.agent_transactions, name="agent_transactions"),
    path("agent/profil/", views_agent.agent_profile, name="agent_profile"),

    # Admin
    path("admin-panel/", views_admin.admin_overview, name="admin_overview"),
    path("admin-panel/utilisateurs/", views_admin.admin_users, name="admin_users"),
    path("admin-panel/utilisateurs/<int:pk>/toggle/", views_admin.admin_user_toggle, name="admin_user_toggle"),
    path("admin-panel/utilisateurs/<int:pk>/supprimer/", views_admin.admin_user_delete, name="admin_user_delete"),
    path("admin-panel/proprietes/", views_admin.admin_properties, name="admin_properties"),
    path("admin-panel/proprietes/ajouter/", views_admin.admin_property_create, name="admin_property_create"),
    path("admin-panel/proprietes/<int:pk>/modifier/", views_admin.admin_property_edit, name="admin_property_edit"),
    path("admin-panel/proprietes/<int:pk>/valider/", views_admin.admin_property_validate, name="admin_property_validate"),
    path("admin-panel/proprietes/<int:pk>/supprimer/", views_admin.admin_property_delete, name="admin_property_delete"),
    path("admin-panel/transactions/", views_admin.admin_transactions, name="admin_transactions"),
    path("admin-panel/parametres/", views_admin.admin_settings, name="admin_settings"),
]
