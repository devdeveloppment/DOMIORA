from django.urls import path
from . import views, views_ai

app_name = "properties"

urlpatterns = [
    path("", views.property_list, name="list"),
    path("recherche-ia/", views_ai.ai_search, name="ai_search"),
    path("recherche-ia/api/", views_ai.ai_search_api, name="ai_search_api"),
    path("comparer/analyse/", views_ai.compare_analysis, name="compare_analysis"),
    path("alertes/enregistrer/", views.save_search_alert, name="save_search_alert"),
    path("alertes/mes/", views.my_alerts, name="my_alerts"),
    path("comparer/", views.compare_properties, name="compare"),
    path("favori/<int:pk>/", views.toggle_favorite, name="toggle_favorite"),
    path("<slug:slug>/", views.property_detail, name="detail"),
    path("<slug:slug>/payer/", views.property_payment_redirect, name="payment_redirect"),
    path("<slug:slug>/confirmation/", views.property_payment_confirmation, name="payment_confirmation"),
    path("<slug:slug>/notification/", views.property_payment_notify, name="payment_notify"),
]
