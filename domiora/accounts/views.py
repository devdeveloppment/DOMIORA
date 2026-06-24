from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from .forms import RegisterForm, ProfileForm
from .models import User
from agents.models import Agent


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:redirect")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.role == User.Role.AGENT:
                Agent.objects.get_or_create(user=user)
            login(request, user)
            try:
                send_mail(
                    subject="Bienvenue sur DOMIORA",
                    message=f"Bonjour {user.first_name},\n\nVotre compte DOMIORA a bien été créé. Trouvez, louez ou devenez propriétaire, en toute simplicité.\n\nL'équipe DOMIORA",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f"Bienvenue sur DOMIORA, {user.first_name} !")
            return redirect("dashboard:redirect")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})
