from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.models import User
from dashboard.decorators import role_required
from properties.models import Property

from . import services
from .models import AdminDecision, MissionEvidence, VerificationMission

MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
ALLOWED_EVIDENCE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class EvidenceForm(forms.Form):
    image = forms.ImageField()
    caption = forms.CharField(max_length=200, required=False)
    device_captured_at = forms.CharField(required=False)
    latitude = forms.CharField(required=False)
    longitude = forms.CharField(required=False)
    accuracy = forms.CharField(required=False)

    def clean_image(self):
        img = self.cleaned_data["image"]
        if img.size > MAX_EVIDENCE_BYTES:
            raise forms.ValidationError("Photo trop volumineuse (8 Mo maximum).")
        if getattr(img, "content_type", "") not in ALLOWED_EVIDENCE_TYPES:
            raise forms.ValidationError("Formats acceptés : JPEG, PNG, WebP.")
        return img


def _decimal(value, low, high):
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return d.quantize(Decimal("0.000001")) if low <= d <= high else None


# --- Espace administrateur --------------------------------------------------

@role_required(User.Role.ADMIN)
def admin_missions(request):
    missions = VerificationMission.objects.select_related("owner", "verifier", "property")
    status = request.GET.get("status")
    if status:
        missions = missions.filter(status=status)
    page_obj = Paginator(missions, 20).get_page(request.GET.get("page"))
    return render(request, "field_verification/admin_list.html", {
        "page_obj": page_obj, "status_filter": status, "statuses": VerificationMission.Status.choices,
        "dash_role": "admin", "active": "missions",
    })


@role_required(User.Role.ADMIN)
def admin_mission_create(request):
    owners = User.objects.filter(role=User.Role.OWNER, is_active=True).order_by("last_name", "username")
    verifiers = User.objects.filter(role=User.Role.VERIFIER, is_active=True).order_by("last_name")
    if request.method == "POST":
        owner = get_object_or_404(owners, pk=request.POST.get("owner"))
        prop = None
        if request.POST.get("property"):
            prop = get_object_or_404(Property, pk=request.POST["property"], owner=owner)
        verifier = verifiers.filter(pk=request.POST.get("verifier")).first() if request.POST.get("verifier") else None
        try:
            mission = services.create_mission(request.user, owner, prop, request.POST.get("instructions", ""), verifier)
        except services.TransitionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Mission #{mission.pk} créée.")
            return redirect("dashboard:admin_mission_detail", pk=mission.pk)
    preselected = request.GET.get("owner")
    return render(request, "field_verification/admin_create.html", {
        "owners": owners, "verifiers": verifiers, "preselected": preselected,
        "owner_properties": Property.objects.filter(owner_id=preselected) if preselected and preselected.isdigit() else [],
        "dash_role": "admin", "active": "missions",
    })


@role_required(User.Role.ADMIN)
def admin_mission_detail(request, pk):
    mission = get_object_or_404(
        VerificationMission.objects.select_related("owner", "verifier", "property", "identity_request"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "assign":
                verifier = get_object_or_404(User, pk=request.POST.get("verifier"), role=User.Role.VERIFIER)
                services.assign(request.user, mission, verifier)
            elif action == "request_info":
                services.request_info(request.user, mission, request.POST.get("feedback", ""))
            elif action in AdminDecision.Decision.values:
                services.decide(request.user, mission, action, request.POST.get("reason", ""))
            else:
                raise services.TransitionError("Action inconnue.")
        except services.TransitionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Mission mise à jour.")
        return redirect("dashboard:admin_mission_detail", pk=pk)
    return render(request, "field_verification/admin_detail.html", {
        "mission": mission, "verifiers": User.objects.filter(role=User.Role.VERIFIER, is_active=True),
        "decisions": AdminDecision.Decision.choices, "dash_role": "admin", "active": "missions",
    })


@role_required(User.Role.ADMIN)
def admin_verifier_create(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        try:
            if len(password) < 10:
                raise ValidationError("Le mot de passe doit contenir au moins 10 caractères.")
            validate_password(password)
            password_error = ""
        except ValidationError as exc:
            password_error = " ".join(exc.messages)
        if not username or password_error:
            messages.error(request, password_error or "Identifiant requis.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Cet identifiant existe déjà.")
        else:
            User.objects.create_user(
                username=username, password=password, role=User.Role.VERIFIER,
                first_name=request.POST.get("first_name", ""), last_name=request.POST.get("last_name", ""),
                email=request.POST.get("email", ""), phone=request.POST.get("phone", ""),
            )
            messages.success(request, "Compte vérificateur créé.")
    return redirect("dashboard:admin_missions")


# --- Espace vérificateur ----------------------------------------------------

def _verifier_mission(request, pk):
    # 404 (et non 403) : on ne révèle pas l'existence des missions d'autrui.
    return get_object_or_404(
        VerificationMission.objects.select_related("owner", "property"), pk=pk, verifier=request.user)


@role_required(User.Role.VERIFIER)
def verifier_home(request):
    missions = VerificationMission.objects.filter(verifier=request.user).select_related("owner", "property")
    open_missions = missions.exclude(status=VerificationMission.Status.CLOSED)
    return render(request, "field_verification/verifier_home.html", {
        "open_missions": open_missions, "closed_missions": missions.filter(status=VerificationMission.Status.CLOSED)[:20],
        "dash_role": "verifier", "active": "missions",
    })


@role_required(User.Role.VERIFIER)
def verifier_mission(request, pk):
    mission = _verifier_mission(request, pk)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "schedule":
                when = parse_datetime(request.POST.get("scheduled_for", ""))
                if not when:
                    raise services.TransitionError("Date de visite invalide.")
                if timezone.is_naive(when):
                    when = timezone.make_aware(when)
                services.schedule(request.user, mission, when)
            elif action == "start":
                services.start(request.user, mission)
            elif action in ("save", "submit"):
                updates = {
                    item["key"]: {"checked": request.POST.get(f"check_{item['key']}") == "on",
                                  "note": request.POST.get(f"note_{item['key']}", "")}
                    for item in mission.checklist
                }
                services.save_report(request.user, mission, updates, request.POST.get("observations", ""),
                                     request.POST.get("report", ""), request.POST.get("recommendation", ""))
                if action == "submit":
                    services.submit_report(request.user, mission)
            else:
                raise services.TransitionError("Action inconnue.")
        except services.TransitionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Mission enregistrée.")
        return redirect("dashboard:verifier_mission", pk=pk)
    return render(request, "field_verification/verifier_mission.html", {
        "mission": mission, "evidence_form": EvidenceForm(),
        "recommendations": mission.Recommendation.choices, "dash_role": "verifier", "active": "missions",
    })


@role_required(User.Role.VERIFIER)
@require_POST
def verifier_evidence_upload(request, pk):
    mission = _verifier_mission(request, pk)
    if not mission.verifier_can_edit or mission.status not in (mission.Status.IN_PROGRESS, mission.Status.INFO_REQUESTED):
        messages.error(request, "Démarrez la mission pour ajouter des preuves.")
        return redirect("dashboard:verifier_mission", pk=pk)
    form = EvidenceForm(request.POST, request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            messages.error(request, errors[0])
        return redirect("dashboard:verifier_mission", pk=pk)
    lat = _decimal(form.cleaned_data["latitude"], -90, 90)
    lng = _decimal(form.cleaned_data["longitude"], -180, 180)
    captured = parse_datetime(form.cleaned_data["device_captured_at"] or "")
    try:
        accuracy = int(float(form.cleaned_data["accuracy"])) if form.cleaned_data["accuracy"] else None
    except ValueError:
        accuracy = None
    MissionEvidence.objects.create(
        mission=mission, uploaded_by=request.user, image=form.cleaned_data["image"],
        caption=form.cleaned_data["caption"], device_captured_at=captured,
        latitude=lat if lng is not None else None, longitude=lng if lat is not None else None,
        accuracy_m=accuracy if accuracy and accuracy >= 0 else None,
        location_source=MissionEvidence.LocationSource.BROWSER if lat is not None and lng is not None else MissionEvidence.LocationSource.NONE,
    )
    messages.success(request, "Preuve ajoutée.")
    return redirect("dashboard:verifier_mission", pk=pk)


def evidence_file(request, pk):
    """Sert une preuve uniquement à l'administrateur ou au vérificateur de la mission."""
    if not request.user.is_authenticated:
        raise Http404
    evidence = get_object_or_404(MissionEvidence.objects.select_related("mission"), pk=pk)
    user = request.user
    allowed = user.is_superuser or user.role == User.Role.ADMIN or (
        user.role == User.Role.VERIFIER and evidence.mission.verifier_id == user.pk)
    if not allowed:
        raise Http404
    response = FileResponse(evidence.image.open("rb"))
    response["Cache-Control"] = "private, no-store"
    return response
