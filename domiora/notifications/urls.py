from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("<int:pk>/lue/", views.mark_read, name="mark_read"),
    path("tout-marquer-lu/", views.mark_all_read, name="mark_all_read"),
]
