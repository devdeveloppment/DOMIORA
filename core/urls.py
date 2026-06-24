from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("a-propos/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("api/recherche-suggestions/", views.search_suggestions, name="search_suggestions"),
    path("api/assistant/", views.assistant_chat, name="assistant_chat"),
]
