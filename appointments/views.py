from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings

from .models import Appointment
from agents.models import Agent
from properties.models import Property
from notifications.models import Notification


def book_appointment(request, agent_id):
    """Allow both logged-in users and guests to book appointments"""
    agent = get_object_or_404(Agent, pk=agent_id)
    property_id = request.POST.get("property_id") or request.GET.get("property")
    property_obj = Property.objects.filter(pk=property_id).first() if property_id else None

    if request.method == "POST":
        from .forms import AppointmentForm
        form = AppointmentForm(request.POST, user=request.user)
        
        if form.is_valid():
            # Handle guest users (not logged in)
            if not request.user.is_authenticated:
                guest_name = form.cleaned_data.get("guest_name", "")
                guest_email = form.cleaned_data.get("guest_email", "")
                guest_phone = form.cleaned_data.get("guest_phone", "")
                
                # Create a client account automatically
                from accounts.models import User
                import random
                import string
                
                # Generate unique username
                username = f"guest_{guest_name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
                while User.objects.filter(username=username).exists():
                    username = f"guest_{guest_name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
                
                # Generate random password
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                
                guest_user = User.objects.create_user(
                    username=username,
                    email=guest_email,
                    password=password,
                    first_name=guest_name.split()[0] if ' ' in guest_name else guest_name,
                    last_name=guest_name.split()[-1] if ' ' in guest_name else '',
                    phone=guest_phone,
                    role=User.Role.CLIENT
                )
                
                # Auto-login the guest user
                from django.contrib.auth import login
                login(request, guest_user)
                
                # Force session role to 'client'
                request.session['dash_role'] = 'client'
                request.session.modified = True
                
                user = guest_user
            else:
                user = request.user
            
            appt = form.save(commit=False)
            appt.user = user
            appt.agent = agent
            appt.property = property_obj
            appt.save()
            Notification.objects.create(
                user=agent.user, title="Nouvelle demande de rendez-vous",
                message=f"{user.get_full_name()} souhaite un rendez-vous le {appt.scheduled_at:%d/%m/%Y à %H:%M}.",
                notification_type="demande", link="/dashboard/proprietaire/rendez-vous/",
            )
            try:
                send_mail(
                    "DOMIORA - Nouvelle demande de rendez-vous",
                    f"{user.get_full_name()} a demandé un rendez-vous le {appt.scheduled_at:%d/%m/%Y à %H:%M}.",
                    settings.DEFAULT_FROM_EMAIL, [agent.user.email], fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, "Votre demande de rendez-vous a été envoyée à l'agent.")
            return redirect(property_obj.get_absolute_url() if property_obj else agent.get_absolute_url())
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def my_appointments(request):
    appts = Appointment.objects.filter(user=request.user).select_related("agent__user", "property")
    return render(request, "appointments/my_appointments.html", {"appointments": appts, "dash_role": "client", "active": "appointments"})


@login_required
def agent_appointments(request):
    agent = Agent.objects.filter(user=request.user).first()
    appts = Appointment.objects.filter(agent=agent).select_related("user", "property") if agent else []
    return render(request, "appointments/agent_appointments.html", {"appointments": appts, "dash_role": "owner", "active": "appointments"})


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
