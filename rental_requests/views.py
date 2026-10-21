from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import PropertyRequest
from properties.models import Property
from notifications.models import Notification
from accounts.models import User
import json
import logging

logger = logging.getLogger(__name__)


def _request_response(request, ok, text, property_obj=None, status=200, **extra):
    """Réponse JSON (appel AJAX) ou redirection avec message (formulaire classique)."""
    if request.content_type == "application/json" or status == 403:  # refus d'accès : toujours 403 explicite
        return JsonResponse({"success": ok, "message": text, **extra}, status=status)
    from django.contrib import messages

    (messages.success if ok else messages.error)(request, text)
    if property_obj is not None:
        return redirect("properties:detail", slug=property_obj.slug)
    return redirect("properties:list")


@require_http_methods(["POST"])
def create_property_request(request):
    """
    Créer une demande de visite, d'achat ou de location.
    Règle métier : compte client connecté disposant d'une relation payée avec le propriétaire.
    """
    from django.utils.dateparse import parse_date

    from payments.relations import has_owner_relation

    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"success": False, "message": "Requête invalide."}, status=400)

    property_id = str(data.get("property_id") or "")
    property_obj = Property.objects.filter(
        pk=property_id if property_id.isdigit() else None,
        is_published=True, is_validated=True, owner__isnull=False,
    ).select_related("owner").first()
    if property_obj is None:
        return _request_response(request, False, "Ce bien n'est plus disponible.", status=404)

    if not (request.user.is_authenticated and request.user.role == User.Role.CLIENT
            and has_owner_relation(request.user, property_obj.owner)):
        return _request_response(
            request, False, "Une mise en relation avec ce propriétaire est nécessaire avant d'envoyer une demande.",
            property_obj, status=403,
        )

    request_type = data.get("request_type") or PropertyRequest.RequestType.VISITE
    if request_type not in PropertyRequest.RequestType.values:
        return _request_response(request, False, "Type de demande inconnu.", property_obj, status=400)
    message = str(data.get("message") or "").strip()[:2000]
    raw_date = str(data.get("move_in_date") or "").strip()
    move_in_date = None
    if raw_date:
        try:
            move_in_date = parse_date(raw_date)
        except ValueError:
            move_in_date = None
        if move_in_date is None:
            return _request_response(request, False, "Date d'emménagement invalide.", property_obj, status=400)

    user = request.user
    # Anti double envoi : une demande identique encore en attente n'est pas recréée.
    existing = PropertyRequest.objects.filter(
        user=user, property=property_obj, request_type=request_type, status=PropertyRequest.Status.EN_ATTENTE,
    ).first()
    if existing:
        return _request_response(
            request, True, "Votre demande est déjà enregistrée et en attente de réponse du propriétaire.",
            property_obj, request_id=existing.id, duplicate=True,
        )

    property_request = PropertyRequest.objects.create(
        user=user,
        property=property_obj,
        request_type=request_type,
        message=message,
        move_in_date=move_in_date,
        status=PropertyRequest.Status.EN_ATTENTE,
    )

    Notification.objects.create(
        user=property_obj.owner,
        notification_type="demande",
        title=f"Nouvelle demande de {property_request.get_request_type_display()}",
        message=f"{user.get_full_name() or user.username} souhaite {property_request.get_request_type_display().lower()} votre bien : {property_obj.title}",
        link="/dashboard/proprietaire/",
    )

    # Envoyer un email au propriétaire
    try:
        subject = f"Nouvelle demande de {property_request.get_request_type_display()} pour {property_obj.title}"
        
        html_message = render_to_string(
            "rental_requests/email_owner_notification.html",
            {
                "owner": property_obj.owner,
                "user": user,
                "property": property_obj,
                "request_type": property_request.get_request_type_display(),
                "message": message,
                "request_id": property_request.id,
                "site_url": f"{request.scheme}://{request.get_host()}",
            }
        )
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [property_obj.owner.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        logger.warning("Notification e-mail de demande impossible (%s)", e.__class__.__name__)
    
    return _request_response(request, True, "Votre demande a été envoyée au propriétaire.", property_obj, request_id=property_request.id)
