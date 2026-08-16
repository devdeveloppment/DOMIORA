from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from django.http import JsonResponse

from .decorators import role_required
from accounts.models import User
from agents.models import Agent, Specialty
from properties.models import Property, PropertyImage
from properties.forms import PropertyForm
from rental_requests.models import PropertyRequest
from transactions.models import Transaction
from notifications.models import Notification
from accounts.forms import ProfileForm


def _get_agent(request):
    agent, _ = Agent.objects.get_or_create(user=request.user)
    return agent


@role_required(User.Role.AGENT)
def agent_overview(request):
    agent = _get_agent(request)
    properties = Property.objects.filter(owner=request.user).select_related("owner")
    requests_qs = PropertyRequest.objects.filter(agent=agent).select_related("property", "user")
    transactions = Transaction.objects.filter(agent=agent).select_related("property", "client")
    revenue = transactions.aggregate(total=Sum("commission_amount"))["total"] or 0
    context = {
        "dash_role": "agent",
        "active": "overview",
        "agent": agent,
        "properties_count": properties.count(),
        "published_count": properties.filter(is_published=True).count(),
        "pending_requests_count": requests_qs.filter(status="en_attente").count(),
        "transactions_count": transactions.count(),
        "revenue": revenue,
        "recent_properties": properties.order_by("-created_at")[:5],
        "recent_requests": requests_qs.order_by("-created_at")[:5],
    }
    return render(request, "dashboard/agent/overview.html", context)


@role_required(User.Role.AGENT)
def agent_properties(request):
    properties = Property.objects.filter(owner=request.user).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/agent/properties.html", {"page_obj": page_obj, "agent": _get_agent(request), "dash_role": "agent", "active": "properties"})


@role_required(User.Role.AGENT)
def agent_property_create(request):
    if request.method == "POST":
        form = PropertyForm(request.POST)
        if form.is_valid():
            property_obj = form.save(commit=False)
            property_obj.owner = request.user
            # Force la propriété à être en attente de validation et non publiée
            property_obj.is_published = False
            property_obj.is_validated = False
            property_obj.validation_status = Property.ValidationStatus.PENDING
            property_obj.save()
            form.save_m2m()
            for i, uploaded in enumerate(request.FILES.getlist("images")):
                PropertyImage.objects.create(property=property_obj, image=uploaded, is_primary=(i == 0), order=i)
            messages.success(request, "Le bien a été ajouté avec succès et est en attente de validation par l'administrateur.")
            return redirect("dashboard:agent_properties")
    else:
        form = PropertyForm()
    return render(request, "dashboard/agent/property_form.html", {"form": form, "is_edit": False, "dash_role": "agent", "active": "properties"})


@role_required(User.Role.AGENT)
def agent_property_edit(request, pk):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        form = PropertyForm(request.POST, instance=property_obj)
        if form.is_valid():
            updated_property = form.save(commit=False)
            # Si la propriété n'est pas encore validée, la remettre en attente de validation
            if not property_obj.is_validated:
                updated_property.is_published = False
                updated_property.validation_status = Property.ValidationStatus.PENDING
            updated_property.save()
            form.save_m2m()
            for i, uploaded in enumerate(request.FILES.getlist("images")):
                PropertyImage.objects.create(property=property_obj, image=uploaded, order=property_obj.images.count() + i)
            messages.success(request, "Le bien a été mis à jour.")
            return redirect("dashboard:agent_properties")
    else:
        form = PropertyForm(instance=property_obj)
    return render(request, "dashboard/agent/property_form.html", {"form": form, "is_edit": True, "property": property_obj, "dash_role": "agent", "active": "properties"})


@role_required(User.Role.AGENT)
def agent_property_delete(request, pk):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        property_obj.delete()
        messages.success(request, "Le bien a été supprimé.")
    return redirect("dashboard:agent_properties")


@role_required(User.Role.AGENT)
def agent_property_toggle_publish(request, pk):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    property_obj.is_published = not property_obj.is_published
    property_obj.save(update_fields=["is_published"])
    return redirect("dashboard:agent_properties")


@role_required(User.Role.AGENT)
def agent_property_image_delete(request, pk, image_id):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    PropertyImage.objects.filter(pk=image_id, property=property_obj).delete()
    return redirect("dashboard:agent_property_edit", pk=property_obj.pk)


@role_required(User.Role.AGENT)
def agent_requests(request):
    agent = _get_agent(request)
    requests_qs = PropertyRequest.objects.filter(agent=agent).select_related("property", "user").order_by("-created_at")
    status = request.GET.get("status")
    if status:
        requests_qs = requests_qs.filter(status=status)
    paginator = Paginator(requests_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/agent/requests.html", {"page_obj": page_obj, "dash_role": "agent", "active": "requests"})


@role_required(User.Role.AGENT)
def agent_request_update_status(request, pk, status):
    agent = _get_agent(request)
    property_request = get_object_or_404(PropertyRequest, pk=pk, agent=agent)
    if status in ("acceptee", "rejetee"):
        property_request.status = status
        property_request.save(update_fields=["status"])
        Notification.objects.create(
            user=property_request.user,
            title=f"Votre demande a été {'acceptée' if status == 'acceptee' else 'rejetée'}",
            message=f"Votre demande pour « {property_request.property.title} » a été {'acceptée' if status == 'acceptee' else 'rejetée'} par l'agent.",
            notification_type="demande",
            link=property_request.property.get_absolute_url(),
        )
        try:
            send_mail(
                subject="DOMIORA - Mise à jour de votre demande",
                message=f"Bonjour {property_request.user.first_name},\n\nVotre demande pour « {property_request.property.title} » a été {'acceptée' if status == 'acceptee' else 'rejetée'}.\n\nL'équipe DOMIORA",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[property_request.user.email],
                fail_silently=True,
            )
        except Exception:
            pass
        messages.success(request, "Statut de la demande mis à jour.")
    return redirect("dashboard:agent_requests")


@role_required(User.Role.AGENT)
def agent_transactions(request):
    agent = _get_agent(request)
    transactions = Transaction.objects.filter(agent=agent).select_related("property", "client").order_by("-transaction_date")
    paginator = Paginator(transactions, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    revenue = transactions.aggregate(total=Sum("commission_amount"))["total"] or 0
    return render(request, "dashboard/agent/transactions.html", {"page_obj": page_obj, "revenue": revenue, "dash_role": "agent", "active": "transactions"})


@role_required(User.Role.AGENT)
def agent_profile(request):
    agent = _get_agent(request)
    if request.method == "POST":
        user_form = ProfileForm(request.POST, request.FILES, instance=request.user)
        agent.agency_name = request.POST.get("agency_name", agent.agency_name)
        agent.license_number = request.POST.get("license_number", agent.license_number)
        agent.bio = request.POST.get("agent_bio", agent.bio)
        agent.facebook = request.POST.get("facebook", agent.facebook)
        agent.instagram = request.POST.get("instagram", agent.instagram)
        agent.linkedin = request.POST.get("linkedin", agent.linkedin)
        agent.twitter = request.POST.get("twitter", agent.twitter)
        if user_form.is_valid():
            user_form.save()
            agent.save()
            messages.success(request, "Profil agent mis à jour.")
            return redirect("dashboard:agent_profile")
    else:
        user_form = ProfileForm(instance=request.user)
    return render(request, "dashboard/agent/profile.html", {"form": user_form, "agent": agent, "all_specialties": Specialty.objects.all(), "dash_role": "agent", "active": "profile"})


@role_required(User.Role.AGENT)
def agent_subscription(request):
    return render(request, "dashboard/agent/subscription.html", {"dash_role": "agent", "active": "subscription", "agent": _get_agent(request), "current_sub": None, "plans": [], "properties_count": Property.objects.filter(owner=request.user).count()})


@role_required(User.Role.AGENT)
def agent_subscription_checkout(request, plan_id):
    messages.info(request, "Le modèle d'abonnement agent a été désactivé. La publication est désormais gratuite.")
    return redirect("dashboard:agent_subscription")


@role_required(User.Role.AGENT)
def agent_verify_flutterwave_payment(request):
    return JsonResponse({"status": "error", "message": "Les abonnements agent ont été supprimés."}, status=410)


@role_required(User.Role.AGENT)
def agent_verify_fedapay_payment(request):
    return JsonResponse({"status": "error", "message": "Les abonnements agent ont été supprimés."}, status=410)
