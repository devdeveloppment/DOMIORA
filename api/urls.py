from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views

router = DefaultRouter()
router.register("properties", views.PropertyViewSet, basename="property")
router.register("amenities", views.AmenityViewSet, basename="amenity")
router.register("agents", views.AgentViewSet, basename="agent")
router.register("specialties", views.SpecialtyViewSet, basename="specialty")
router.register("favorites", views.FavoriteViewSet, basename="favorite")
router.register("requests", views.PropertyRequestViewSet, basename="propertyrequest")
router.register("transactions", views.TransactionViewSet, basename="transaction")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("me", views.MeView, basename="me")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="api_token_auth"),
    path("verification/submit/", views.verification_submit, name="verification_submit"),
    path("verification/resume/<int:verification_id>/", views.verification_resume, name="verification_resume"),
    path("chat/", views.chat_assistant, name="chat_assistant"),
    path("admin/notifications/", views.admin_notification_webhook, name="admin_notification_webhook"),
    path("", include(router.urls)),
]
