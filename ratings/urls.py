from django.urls import path
from . import views

app_name = "ratings"

urlpatterns = [
    path("create/<int:owner_id>/", views.create_review, name="create"),
    path("owner/<int:owner_id>/", views.owner_reviews, name="owner_reviews"),
]