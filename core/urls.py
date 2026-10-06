from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("a-propos/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("blog/", views.blog, name="blog"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    path("contact/", views.contact, name="contact"),
    path("don/", views.donate, name="donate"),
    path("don/confirmation/", views.donate_confirmation, name="donate_confirmation"),
    path("api/donation-notify/", views.donation_notify, name="donation_notify"),
    path("api/recherche-suggestions/", views.search_suggestions, name="search_suggestions"),
    path("api/assistant/", views.assistant_chat, name="assistant_chat"),
]
