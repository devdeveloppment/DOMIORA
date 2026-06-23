from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings

from .models import Appointment
from agents.models import Agent
from properties.models import Property
from notifications.models import Notification


@login_required
def book_appointment(request, agent_id):
    agent = get_object_or_404(Agent, pk=agent_id)
    property_id = request.POST.get("property_id") or request.GET.get("property")
    property_obj = Property.objects.filter(pk=property_id).first() if property_id else None

    if request.method == "POST":
        from .forms import AppointmentForm
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt = form.save(commit=False)
            appt.user = request.user
            appt.agent = agent
            appt.property = property_obj
            appt.save()
            Notification.objects.create(
                user=agent.user, title="Nouvelle demande de rendez-vous",
                message=f"{request.user.get_full_name()} souhaite un rendez-vous le {appt.scheduled_at:%d/%m/%Y à %H:%M}.",
                notification_type="demande", link="/dashboard/agent/rendez-vous/",
            )
            try:
                send_mail(
                    "DOMIORA - Nouvelle demande de rendez-vous",
                    f"{request.user.get_full_name()} a demandé un rendez-vous le {appt.scheduled_at:%d/%m/%Y à %H:%M}.",
                    settings.DEFAULT_FROM_EMAIL, [agent.user.email], fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, "Votre demande de rendez-vous a été envoyée à l'agent.")
            return redirect(property_obj.get_absolute_url() if property_obj else agent.get_absolute_url())
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def my_appointments(request):
    appts = Appointment.objects.filter(user=request.user).select_related("agent__user", "property")
    return render(request, "appointments/my_appointments.html", {"appointments": appts, "dash_role": "buyer", "active": "appointments"})


@login_required
def agent_appointments(request):
    agent = Agent.objects.filter(user=request.user).first()
    appts = Appointment.objects.filter(agent=agent).select_related("user", "property") if agent else []
    return render(request, "appointments/agent_appointments.html", {"appointments": appts, "dash_role": "agent", "active": "appointments"})


@login_required
def update_appointment_status(request, pk, status):
    agent = Agent.objects.filter(user=request.user).first()
    appt = get_object_or_404(Appointment, pk=pk, agent=agent)
    if status in dict(Appointment.Status.choices):
        appt.status = status
        appt.save(update_fields=["status"])
        Notification.objects.create(
            user=appt.user, title="Mise à jour de votre rendez-vous",
            message=f"Votre rendez-vous du {appt.scheduled_at:%d/%m/%Y à %H:%M} est désormais : {appt.get_status_display()}.",
            notification_type="systeme",
        )
        messages.success(request, "Statut du rendez-vous mis à jour.")
    return redirect("appointments:agent_appointments")
