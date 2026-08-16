from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("nouveau/<int:owner_id>/", views.start_conversation, name="start_conversation"),
    path("<int:pk>/", views.conversation_detail, name="conversation_detail"),
    path("<int:pk>/visite/demander/", views.request_visit, name="request_visit"),
    path("<int:pk>/visite/<int:visit_id>/accepter/", views.accept_visit, name="accept_visit"),
    path("<int:pk>/visite/<int:visit_id>/refuser/", views.refuse_visit, name="refuse_visit"),
    path("<int:pk>/visite/<int:visit_id>/proposer/", views.propose_visit, name="propose_visit"),
    path("<int:pk>/rendezvous/demander/", views.request_rendezvous, name="request_rendezvous"),
    path("<int:pk>/rendezvous/<int:rendezvous_id>/accepter/", views.accept_rendezvous, name="accept_rendezvous"),
    path("<int:pk>/rendezvous/<int:rendezvous_id>/refuser/", views.refuse_rendezvous, name="refuse_rendezvous"),
    path("<int:pk>/rendezvous/<int:rendezvous_id>/proposer/", views.propose_rendezvous, name="propose_rendezvous"),
]
