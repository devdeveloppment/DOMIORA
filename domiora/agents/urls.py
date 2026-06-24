from django.urls import path
from . import views

app_name = "agents"

urlpatterns = [
    path("", views.agent_list, name="list"),
    path("<int:pk>/", views.agent_detail, name="detail"),
]
