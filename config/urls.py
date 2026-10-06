from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dashboard/", include("dashboard.urls")),
    path("", include("core.urls")),
    path("proprietes/", include("properties.urls")),
    path("compte/", include("accounts.urls")),
    path("notifications/", include("notifications.urls")),
    path("messagerie/", include("messaging.urls")),
    path("rendez-vous/", include("appointments.urls")),
    path("demandes/", include("rental_requests.urls")),
    path("api/", include("api.urls")),
    path("avis/", include("ratings.urls")),
    path("favoris/", include("favorites.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
