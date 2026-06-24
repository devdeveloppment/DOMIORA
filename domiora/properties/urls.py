from django.urls import path
from . import views

app_name = "properties"

urlpatterns = [
    path("", views.property_list, name="list"),
    path("comparer/", views.compare_properties, name="compare"),
    path("favori/<int:pk>/", views.toggle_favorite, name="toggle_favorite"),
    path("<slug:slug>/", views.property_detail, name="detail"),
]
