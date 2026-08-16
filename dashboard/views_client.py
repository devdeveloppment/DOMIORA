from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator

from .decorators import role_required
from favorites.models import Favorite
from rental_requests.models import PropertyRequest
from accounts.models import User
from notifications.models import Notification


@role_required(User.Role.CLIENT)
def client_overview(request):
    from properties.models import PropertyUnlock, PropertyView
    from messaging.models import Message
    
    # Check if user has made at least one payment (unlocked a property)
    has_paid = PropertyUnlock.objects.filter(user=request.user).exists()
    
    if not has_paid:
        # Show payment prompt instead of dashboard
        return render(request, "dashboard/client/payment_prompt.html", {
            "dash_role": "client",
            "active": "overview",
        })
    
    favorites_count = Favorite.objects.filter(user=request.user).count()
    requests = PropertyRequest.objects.filter(user=request.user).select_related("property")
    unlocked_count = PropertyUnlock.objects.filter(user=request.user).count()
    
    # Viewed properties history
    viewed_properties = PropertyView.objects.filter(user=request.user).select_related("property").order_by("-viewed_at")[:6]
    
    # Messages count
    messages_count = Message.objects.filter(conversation__buyer=request.user).count()
    notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()

    context = {
        "active": "overview",
        "favorites_count": favorites_count,
        "requests_count": requests.count(),
        "pending_count": requests.filter(status="en_attente").count(),
        "accepted_count": requests.filter(status="acceptee").count(),
        "rejected_count": requests.filter(status="rejetee").count(),
        "recent_requests": requests[:5],
        "recent_favorites": Favorite.objects.filter(user=request.user).select_related("property")[:4],
        "viewed_properties": viewed_properties,
        "messages_count": messages_count,
        "notifications_count": notifications_count,
        "profile_url": request.user.get_absolute_url(),
        "dash_role": "client",
    }
    return render(request, "dashboard/client/overview.html", context)


@role_required(User.Role.CLIENT)
def client_favorites(request):
    favorites = Favorite.objects.filter(user=request.user).select_related("property").prefetch_related("property__images")
    paginator = Paginator(favorites, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/client/favorites.html", {"page_obj": page_obj, "active": "favorites", "dash_role": "client"})


@role_required(User.Role.CLIENT)
def client_history(request):
    """Show complete navigation history for client"""
    from properties.models import PropertyView
    
    # Get all viewed properties, ordered by most recent first
    viewed_properties = (
        PropertyView.objects
        .filter(user=request.user)
        .select_related("property", "property__owner")
        .prefetch_related("property__images")
        .order_by("-viewed_at")
    )
    
    # Pagination
    paginator = Paginator(viewed_properties, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    
    context = {
        "page_obj": page_obj,
        "active": "history",
        "dash_role": "client",
        "total_count": viewed_properties.count(),
    }
    return render(request, "dashboard/client/history.html", context)


@role_required(User.Role.CLIENT)
def client_requests(request):
    from messaging.models import VisitRequest, RendezvousRequest
    
    # Get all types of requests
    property_requests = PropertyRequest.objects.filter(user=request.user).select_related("property", "property__owner")
    visit_requests = VisitRequest.objects.filter(requester=request.user).select_related("conversation", "conversation__property", "conversation__owner")
    rendezvous_requests = RendezvousRequest.objects.filter(requester=request.user).select_related("conversation", "conversation__property", "conversation__owner")
    
    # Combine and sort by date
    all_requests = []
    
    for req in property_requests:
        all_requests.append({
            'type': 'property',
            'object': req,
            'title': req.property.title if req.property else 'Bien inconnu',
            'status': req.status,
            'created_at': req.created_at,
            'property': req.property,
        })
    
    for req in visit_requests:
        all_requests.append({
            'type': 'visit',
            'object': req,
            'title': f"Visite : {req.conversation.property.title if req.conversation.property else 'Bien inconnu'}",
            'status': req.status,
            'created_at': req.created_at,
            'property': req.conversation.property if req.conversation else None,
            'proposed_date': req.proposed_date,
        })
    
    for req in rendezvous_requests:
        all_requests.append({
            'type': 'rendezvous',
            'object': req,
            'title': f"Rendez-vous : {req.conversation.property.title if req.conversation.property else 'Bien inconnu'}",
            'status': req.status,
            'created_at': req.created_at,
            'property': req.conversation.property if req.conversation else None,
            'proposed_date': req.proposed_date,
        })
    
    # Sort by creation date (most recent first)
    all_requests.sort(key=lambda x: x['created_at'], reverse=True)
    
    paginator = Paginator(all_requests, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    
    return render(request, "dashboard/client/requests.html", {
        "page_obj": page_obj, 
        "active": "requests", 
        "dash_role": "client",
        "total_count": len(all_requests)
    })


@role_required(User.Role.CLIENT)
def client_notifications(request):
    notifications = Notification.objects.filter(user=request.user).exclude(link__startswith='/dashboard/admin-panel/')
    context = {
        "dash_role": "client",
        "active": "notifications",
        "notifications": notifications,
    }
    # Ensure session has correct dash_role
    request.session["dash_role"] = "client"
    return render(request, "notifications/list.html", context)


@role_required(User.Role.CLIENT)
def client_unlocked_properties(request):
    """Show all properties this client has unlocked (paid for) - 'Mes mises en relation'."""
    from properties.models import PropertyUnlock
    from messaging.models import Conversation
    
    unlocks = (
        PropertyUnlock.objects
        .filter(user=request.user)
        .select_related("property", "property__owner")
        .prefetch_related("property__images")
        .order_by("-unlocked_at")
    )
    
    # Add conversation information for each unlock
    unlock_data = []
    for unlock in unlocks:
        conversation = Conversation.objects.filter(
            buyer=request.user,
            owner=unlock.property.owner,
            property=unlock.property
        ).first()
        
        unlock_data.append({
            'unlock': unlock,
            'conversation': conversation,
            'has_unread': conversation.unread_count_for(request.user) > 0 if conversation else False
        })
    
    paginator = Paginator(unlock_data, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    
    return render(request, "dashboard/client/my_connections.html", {
        "page_obj": page_obj,
        "active": "connections",
        "dash_role": "client",
        "total_count": len(unlock_data),
    })


@role_required(User.Role.CLIENT)
def client_settings(request):
    return render(request, "dashboard/client/settings.html", {"active": "settings", "dash_role": "client"})


@role_required(User.Role.CLIENT)
def client_messaging(request):
    """Client messaging - redirects to most recent conversation or shows inbox if none"""
    from messaging.models import Conversation
    
    # Ensure session has correct dash_role
    request.session["dash_role"] = "client"
    
    # Get most recent conversation and redirect to it directly
    conversation = (
        Conversation.objects
        .filter(buyer=request.user)
        .select_related("owner", "property")
        .order_by("-updated_at")
        .first()
    )
    
    if conversation:
        # Redirect directly to the most recent conversation
        return redirect("dashboard:client_conversation_detail", pk=conversation.pk)
    
    # If no conversations, show empty inbox
    context = {
        "conversations": Conversation.objects.none(),
        "active": "messaging",
        "dash_role": "client",
    }
    return render(request, "messaging/inbox.html", context)


@role_required(User.Role.CLIENT)
def client_conversation_detail(request, pk):
    """Client conversation detail - shows messages with a specific owner"""
    from messaging.models import Conversation, Message
    from messaging.forms import MessageForm
    
    conversation = get_object_or_404(Conversation, pk=pk, buyer=request.user)
    
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()
            conversation.save()
            
            # Notify owner
            Notification.objects.create(
                user=conversation.owner,
                title="💬 Nouveau message",
                message=msg.body[:120],
                notification_type="systeme",
                link=f"/dashboard/proprietaire/messagerie/{pk}/",
            )
            return redirect("dashboard:client_conversation_detail", pk=pk)
    else:
        form = MessageForm()
    
    # Mark messages as read
    conversation.messages.exclude(sender=request.user).update(is_read=True)
    
    # Ensure session has correct dash_role
    request.session["dash_role"] = "client"
    
    context = {
        "conversation": conversation,
        "form": form,
        "active": "messaging",
        "dash_role": "client",
    }
    return render(request, "messaging/conversation_detail.html", context)
