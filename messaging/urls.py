from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("nouveau/<int:agent_id>/", views.start_conversation, name="start_conversation"),
    path("<int:pk>/", views.conversation_detail, name="conversation_detail"),
]
