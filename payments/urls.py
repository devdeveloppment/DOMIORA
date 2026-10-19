from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("historique/", views.my_payments, name="history"),
    path("webhook/fedapay/", views.fedapay_webhook, name="fedapay_webhook"),
    path("<uuid:reference>/demonstration/", views.simulator, name="simulator"),
    path("<uuid:reference>/demonstration/decision/", views.simulator_decide, name="simulator_decide"),
    path("<uuid:reference>/retour/", views.payment_return, name="return"),
    path("<uuid:reference>/verifier/", views.payment_recheck, name="recheck"),
]
