from django.urls import path
from . import views

app_name = "rental_requests"

urlpatterns = [
    path("create/", views.create_property_request, name="create"),
]
