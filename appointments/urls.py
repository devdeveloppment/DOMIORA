from django.urls import path
from . import views

app_name = "appointments"

urlpatterns = [
    path("reserver/<int:agent_id>/", views.book_appointment, name="book"),
    path("mes-rendez-vous/", views.my_appointments, name="my_appointments"),
    path("agent/", views.agent_appointments, name="agent_appointments"),
    path("agent/<int:pk>/<str:status>/", views.update_appointment_status, name="update_status"),
]
