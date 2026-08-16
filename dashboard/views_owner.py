from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Sum, Count
from django.utils import timezone
from django.db.models.functions import TruncMonth
from datetime import timedelta
import json

from .decorators import role_required
from accounts.models import User
from properties.models import Property, PropertyImage
from properties.forms import PropertyForm
from rental_requests.models import PropertyRequest
from notifications.models import Notification
from accounts.forms import ProfileForm


@role_required(User.Role.OWNER)
def owner_overview(request):
    properties = Property.objects.filter(owner=request.user).select_related("owner").prefetch_related("images")
    requests_qs = PropertyRequest.objects.filter(property__owner=request.user).select_related("property", "user")
    from favorites.models import Favorite
    from messaging.models import Message
    from properties.models import PropertyUnlock, PropertyView

    six_months_ago = timezone.now() - timedelta(days=180)
    
    # Enhanced statistics
    total_views = properties.aggregate(total=Sum('views_count'))['total'] or 0
    total_favorites = Favorite.objects.filter(property__owner=request.user).count()
    total_messages = Message.objects.filter(conversation__owner=request.user).count()
    total_unlocks = PropertyUnlock.objects.filter(property__owner=request.user).count()
    total_visits = requests_qs.filter(request_type="visite").count()
    paid_contacts = total_unlocks
    
    # Property status breakdown
    validated_count = properties.filter(is_validated=True).count()
    rejected_count = properties.filter(validation_status='rejected').count()
    available_count = properties.filter(status='disponible').count()
    sold_count = properties.filter(status='vendu').count()
    rented_count = properties.filter(status='loue').count()
    
    # Request statistics
    accepted_requests = requests_qs.filter(status='acceptee').count()
    rejected_requests = requests_qs.filter(status='rejetee').count()

    views_chart = (
        PropertyView.objects.filter(property__owner=request.user, viewed_at__gte=six_months_ago)
        .annotate(month=TruncMonth("viewed_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    chart_labels = [item["month"].strftime("%b %Y") for item in views_chart]
    chart_values = [item["total"] for item in views_chart]
    
    context = {
        "dash_role": "owner",
        "active": "overview",
        "properties_count": properties.count(),
        "published_count": properties.filter(is_published=True).count(),
        "validated_count": validated_count,
        "pending_validation_count": properties.filter(validation_status='pending').count(),
        "rejected_count": rejected_count,
        "pending_requests_count": requests_qs.filter(status="en_attente").count(),
        "total_requests": requests_qs.count(),
        "total_visits": total_visits,
        "total_views": total_views,
        "total_favorites": total_favorites,
        "total_messages": total_messages,
        "total_unlocks": total_unlocks,
        "paid_contacts": paid_contacts,
        "validated_count": validated_count,
        "rejected_count": rejected_count,
        "available_count": available_count,
        "sold_count": sold_count,
        "rented_count": rented_count,
        "accepted_requests": accepted_requests,
        "rejected_requests": rejected_requests,
        "recent_properties": properties.order_by("-created_at")[:5],
        "recent_requests": requests_qs.order_by("-created_at")[:5],
        "chart_labels": json.dumps(chart_labels),
        "chart_values": json.dumps(chart_values),
    }
    return render(request, "dashboard/owner/overview.html", context)


@role_required(User.Role.OWNER)
def owner_properties(request):
    properties = Property.objects.filter(owner=request.user).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/properties.html", {"page_obj": page_obj, "dash_role": "owner", "active": "properties"})


@role_required(User.Role.OWNER)
def owner_property_create(request):
    if request.user.verification_status != User.VerificationStatus.APPROVED:
        messages.error(request, f"Votre identité doit être vérifiée pour publier un bien. Statut actuel : {request.user.get_verification_status_display()}")
        return redirect("dashboard:owner_verify_identity")

    if request.method == "POST":
        form = PropertyForm(request.POST)
        if form.is_valid():
            property = form.save(commit=False)
            property.owner = request.user
            # Force la propriété à être en attente de validation et non publiée
            property.is_published = False
            property.is_validated = False
            property.validation_status = Property.ValidationStatus.PENDING
            property.save()
            form.save_m2m()
            for i, f in enumerate(request.FILES.getlist("images")):
                PropertyImage.objects.create(property=property, image=f, is_primary=(i == 0), order=i)
                
            if property.images.count() >= 2:
                from properties.tasks import generate_virtual_tour_task
                # Execute directly instead of using Celery delay for development
                generate_virtual_tour_task(property.id)
                messages.success(request, "Le bien a été ajouté avec succès et est en attente de validation par l'administrateur.")
            else:
                messages.success(request, "Le bien a été ajouté avec succès et est en attente de validation par l'administrateur.")
                
            return redirect("dashboard:owner_properties")
    else:
        form = PropertyForm()
    return render(request, "dashboard/owner/property_form.html", {"form": form, "is_edit": False, "dash_role": "owner", "active": "properties"})


@role_required(User.Role.OWNER)
def owner_property_edit(request, pk):
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        form = PropertyForm(request.POST, instance=property)
        if form.is_valid():
            updated_property = form.save(commit=False)
            # Si la propriété n'est pas encore validée, la remettre en attente de validation
            if not property.is_validated:
                updated_property.is_published = False
                updated_property.validation_status = Property.ValidationStatus.PENDING
            updated_property.save()
            form.save_m2m()
            files = request.FILES.getlist("images")
            for i, f in enumerate(files):
                PropertyImage.objects.create(property=property, image=f, order=property.images.count() + i)
                
            if files and property.images.count() >= 2:
                from properties.tasks import generate_virtual_tour_task
                # Execute directly instead of using Celery delay for development
                generate_virtual_tour_task(property.id)
                messages.success(request, "Le bien a été mis à jour et la vidéo a été régénérée.")
            else:
                messages.success(request, "Le bien a été mis à jour.")
                
            return redirect("dashboard:owner_properties")
    else:
        form = PropertyForm(instance=property)
    return render(request, "dashboard/owner/property_form.html", {"form": form, "is_edit": True, "property": property, "dash_role": "owner", "active": "properties"})


@role_required(User.Role.OWNER)
def owner_property_delete(request, pk):
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        property.delete()
        messages.success(request, "Le bien a été supprimé.")
    return redirect("dashboard:owner_properties")


@role_required(User.Role.OWNER)
def owner_property_toggle_publish(request, pk):
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    
    if request.user.verification_status != User.VerificationStatus.APPROVED:
        messages.error(request, "Votre identité doit être vérifiée pour publier/dépublier un bien.")
        return redirect("dashboard:owner_properties")
        
    property.is_published = not property.is_published
    property.save(update_fields=["is_published"])
    return redirect("dashboard:owner_properties")


@role_required(User.Role.OWNER)
def owner_property_image_delete(request, pk, image_id):
    property = get_object_or_404(Property, pk=pk, owner=request.user)
    PropertyImage.objects.filter(pk=image_id, property=property).delete()
    return redirect("dashboard:owner_property_edit", pk=property.pk)


@role_required(User.Role.OWNER)
def owner_requests(request):
    requests_qs = PropertyRequest.objects.filter(property__owner=request.user).select_related("property", "user").order_by("-created_at")
    status = request.GET.get("status")
    if status:
        requests_qs = requests_qs.filter(status=status)
    paginator = Paginator(requests_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/requests.html", {"page_obj": page_obj, "dash_role": "owner", "active": "requests"})


@role_required(User.Role.OWNER)
def owner_request_update_status(request, pk, status):
    property_request = get_object_or_404(PropertyRequest, pk=pk, property__owner=request.user)
    if status in ("acceptee", "rejetee"):
        property_request.status = status
        property_request.save(update_fields=["status"])
        Notification.objects.create(
            user=property_request.user,
            title=f"Votre demande a été {'acceptée' if status == 'acceptee' else 'rejetée'}",
            message=f"Votre demande pour « {property_request.property.title} » a été {'acceptée' if status == 'acceptee' else 'rejetée'} par le propriétaire.",
            notification_type="demande",
            link=property_request.property.get_absolute_url(),
        )
        try:
            send_mail(
                subject=f"DOMIORA - Mise à jour de votre demande",
                message=f"Bonjour {property_request.user.first_name},\n\nVotre demande pour « {property_request.property.title} » a été {'acceptée' if status == 'acceptee' else 'rejetée'}.\n\nL'équipe DOMIORA",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[property_request.user.email],
                fail_silently=True,
            )
        except Exception:
            pass
        messages.success(request, "Statut de la demande mis à jour.")
    return redirect("dashboard:owner_requests")


@role_required(User.Role.OWNER)
def owner_verify_identity(request):
    from accounts.models import IdentityVerificationRequest
    
    # Get the latest verification request for this owner
    latest_request = request.user.verification_requests.first()
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"=== VERIFICATION PAGE LOAD ===")
    logger.info(f"Owner: {request.user.username} (ID: {request.user.id})")
    logger.info(f"Verification status: {request.user.verification_status}")
    logger.info(f"Latest request: {latest_request}")
    if latest_request:
        logger.info(f"Request ID: {latest_request.id}, Status: {latest_request.status}")
    
    if request.method == "POST":
        logger.info(f"=== FORM SUBMISSION ===")
        logger.info(f"POST data keys: {list(request.POST.keys())}")
        logger.info(f"FILES keys: {list(request.FILES.keys())}")
        
        id_document_front = request.FILES.get("id_document_front")
        id_document_back = request.FILES.get("id_document_back")
        id_document_type = request.POST.get("id_document_type", "")
        id_document_number = request.POST.get("id_document_number", "")
        
        logger.info(f"Front document: {id_document_front}")
        logger.info(f"Back document: {id_document_back}")
        logger.info(f"Document type: {id_document_type}")
        logger.info(f"Document number: {id_document_number}")
        
        if not id_document_front or not id_document_back:
            logger.error("Missing documents")
            messages.error(request, "Veuillez fournir les deux faces de votre pièce d'identité.")
            return redirect("dashboard:owner_verify_identity")
        
        try:
            # Create new verification request
            verification_request = IdentityVerificationRequest.objects.create(
                owner=request.user,
                id_document_front=id_document_front,
                id_document_back=id_document_back,
                id_document_type=id_document_type,
                id_document_number=id_document_number,
                status=IdentityVerificationRequest.Status.PENDING
            )
            
            logger.info(f"✓ Created verification request #{verification_request.id}")
            logger.info(f"✓ Front image: {verification_request.id_document_front.name}")
            logger.info(f"✓ Back image: {verification_request.id_document_back.name}")
            
            # Update owner's verification status
            request.user.verification_status = User.VerificationStatus.PENDING
            request.user.save(update_fields=["verification_status"])
            logger.info(f"✓ Updated owner status to PENDING")
            
            # Send notification to owner
            Notification.objects.create(
                user=request.user,
                title="Demande de vérification soumise",
                message="Vos documents ont été envoyés avec succès. Ils seront examinés par un administrateur. Vous recevrez une notification dès que votre identité sera validée.",
                notification_type="systeme",
                link="/dashboard/proprietaire/verification-identite/"
            )
            logger.info(f"✓ Notification sent to owner")
            
            # Send notification to all admins
            admins = User.objects.filter(role=User.Role.ADMIN)
            logger.info(f"✓ Found {admins.count()} admin(s)")
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title="Nouvelle demande de vérification d'identité",
                    message=f"Le propriétaire {request.user.get_full_name() or request.user.username} vient de soumettre ses documents d'identité. Veuillez examiner les pièces et valider ou refuser la demande.",
                    notification_type="systeme",
                    link="/dashboard/admin-panel/verifications-identite/"
                )
            logger.info(f"✓ Notifications sent to admins")
            
            messages.success(request, "Vos documents ont été envoyés avec succès. Ils seront examinés par un administrateur. Vous recevrez une notification dès que votre identité sera validée.")
            return redirect("dashboard:owner_verify_identity")
            
        except Exception as e:
            logger.error(f"Error creating verification request: {e}")
            import traceback
            logger.error(traceback.format_exc())
            messages.error(request, f"Erreur lors de la soumission: {str(e)}")
            return redirect("dashboard:owner_verify_identity")
    
    context = {
        "dash_role": "owner",
        "active": "verification",
        "latest_request": latest_request,
    }
    return render(request, "dashboard/owner/verify_identity.html", context)


@role_required(User.Role.OWNER)
def owner_profile(request):
    if request.method == "POST":
        user_form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("dashboard:owner_profile")
    else:
        user_form = ProfileForm(instance=request.user)
    return render(request, "dashboard/owner/profile.html", {"form": user_form, "dash_role": "owner", "active": "profile"})


@role_required(User.Role.OWNER)
def owner_notifications(request):
    notifications = Notification.objects.filter(user=request.user).exclude(link__startswith='/dashboard/admin-panel/')
    context = {
        "dash_role": "owner",
        "active": "notifications",
        "notifications": notifications,
    }
    return render(request, "notifications/list.html", context)

@role_required(User.Role.OWNER)
def owner_pending_properties(request):
    properties = Property.objects.filter(owner=request.user, is_published=False).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/properties.html", {"page_obj": page_obj, "dash_role": "owner", "active": "pending_properties", "title_override": "Annonces en attente"})

@role_required(User.Role.OWNER)
def owner_published_properties(request):
    properties = Property.objects.filter(owner=request.user, is_published=True).order_by("-created_at")
    paginator = Paginator(properties, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/owner/properties.html", {"page_obj": page_obj, "dash_role": "owner", "active": "published_properties", "title_override": "Annonces validées"})

@role_required(User.Role.OWNER)
def owner_stats(request):
    return render(request, "dashboard/owner/stats.html", {"dash_role": "owner", "active": "stats"})

@role_required(User.Role.OWNER)
def owner_settings(request):
    return render(request, "dashboard/owner/settings.html", {"dash_role": "owner", "active": "settings"})


@role_required(User.Role.OWNER)
def owner_messaging(request):
    """Owner messaging - redirects to most recent conversation or shows inbox if none"""
    from messaging.models import Conversation
    
    # Ensure session has correct dash_role
    request.session["dash_role"] = "owner"
    
    # Get most recent conversation and redirect to it directly
    conversation = (
        Conversation.objects
        .filter(owner=request.user)
        .select_related("buyer", "property")
        .order_by("-updated_at")
        .first()
    )
    
    if conversation:
        # Redirect directly to the most recent conversation
        return redirect("dashboard:owner_conversation_detail", pk=conversation.pk)
    
    # If no conversations, show empty inbox
    context = {
        "conversations": Conversation.objects.none(),
        "active": "messaging",
        "dash_role": "owner",
    }
    return render(request, "messaging/inbox.html", context)


@role_required(User.Role.OWNER)
def owner_conversation_detail(request, pk):
    """Owner conversation detail - shows messages with a specific client"""
    from messaging.models import Conversation, Message
    from messaging.forms import MessageForm
    
    conversation = get_object_or_404(Conversation, pk=pk, owner=request.user)
    
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()
            conversation.save()
            
            # Notify client
            Notification.objects.create(
                user=conversation.buyer,
                title="💬 Nouveau message",
                message=msg.body[:120],
                notification_type="systeme",
                link=f"/dashboard/client/messagerie/{pk}/",
            )
            return redirect("dashboard:owner_conversation_detail", pk=pk)
    else:
        form = MessageForm()
    
    # Mark messages as read
    conversation.messages.exclude(sender=request.user).update(is_read=True)
    
    # Ensure session has correct dash_role
    request.session["dash_role"] = "owner"
    
    context = {
        "conversation": conversation,
        "form": form,
        "active": "messaging",
        "dash_role": "owner",
    }
    return render(request, "messaging/conversation_detail.html", context)
