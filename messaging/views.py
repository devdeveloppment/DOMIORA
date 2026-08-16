from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.http import JsonResponse

from .models import Conversation, Message, VisitRequest, RendezvousRequest
from .forms import MessageForm, VisitRequestForm, VisitResponseForm, RendezvousRequestForm, RendezvousResponseForm
from accounts.models import User
from properties.models import Property, PropertyUnlock
from notifications.models import Notification


def _has_paid_for_property(user, property_obj):
    """Return True if user has unlocked this property (paid or is owner/admin)."""
    if not user.is_authenticated:
        return False
    if user.role in [User.Role.OWNER, User.Role.ADMIN] or user.is_superuser:
        return True
    if property_obj and property_obj.owner == user:
        return True
    if property_obj:
        return PropertyUnlock.objects.filter(user=user, property=property_obj).exists()
    return False


@login_required
def start_conversation(request, owner_id):
    """
    Start or retrieve a conversation with a property owner.
    Requires a valid PropertyUnlock for the target property.
    """
    owner = get_object_or_404(User, pk=owner_id, role=User.Role.OWNER)
    property_id = request.POST.get("property_id") or request.GET.get("property")
    property_obj = Property.objects.filter(pk=property_id).first() if property_id else None

    # ── Security: Verify owner matches property owner ───────────────────────
    if property_obj and property_obj.owner != owner:
        django_messages.error(
            request,
            "Erreur : Le propriétaire spécifié ne correspond pas à ce bien.",
        )
        return redirect("properties:detail", slug=property_obj.slug)
    # ────────────────────────────────────────────────────────────────────────

    # ── Payment gate ────────────────────────────────────────────────────────
    if not _has_paid_for_property(request.user, property_obj):
        slug = property_obj.slug if property_obj else ""
        django_messages.error(
            request,
            "Vous devez effectuer les frais de mise en relation (500 FCFA) avant de contacter ce propriétaire.",
        )
        if slug:
            return redirect("properties:payment_redirect", slug=slug)
        return redirect("properties:list")
    # ────────────────────────────────────────────────────────────────────────

    initial_message = request.POST.get("message", "").strip()

    conversation, created = Conversation.objects.get_or_create(
        buyer=request.user, owner=owner, property=property_obj,
    )
    if initial_message:
        Message.objects.create(conversation=conversation, sender=request.user, body=initial_message)
        Notification.objects.create(
            user=owner,
            title="💬 Nouveau message",
            message=f"{request.user.get_full_name() or request.user.username} vous a envoyé un message pour « {property_obj.title if property_obj else 'un bien'} ».",
            notification_type="systeme",
            link=f"/messagerie/{conversation.pk}/",
        )
    return redirect("messaging:conversation_detail", pk=conversation.pk)


@login_required
def inbox(request):
    dash_role = request.session.get("dash_role")

    is_owner = (request.user.role == User.Role.OWNER) or (
        dash_role == "owner" and getattr(request.user, "is_superuser", False)
    )

    if is_owner:
        conversations = list(
            Conversation.objects.filter(owner=request.user).select_related("buyer", "property")
        )
    else:
        conversations = list(
            Conversation.objects.filter(buyer=request.user).select_related("owner", "property")
        )

    for c in conversations:
        c.unread = c.unread_count_for(request.user)

    return render(
        request,
        "messaging/inbox.html",
        {
            "conversations": conversations,
            "active": "messages",
            "dash_role": "owner" if is_owner else "client",
        },
    )


@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)

    # Security: only participants can access the conversation
    if request.user not in (conversation.buyer, conversation.owner):
        django_messages.error(request, "Accès refusé.")
        return redirect("messaging:inbox")

    # Payment gate: buyer must have unlocked the property
    if request.user == conversation.buyer:
        if not _has_paid_for_property(request.user, conversation.property):
            slug = conversation.property.slug if conversation.property else ""
            django_messages.error(
                request,
                "Vous devez effectuer les frais de mise en relation (500 FCFA) pour accéder à cette conversation.",
            )
            if slug:
                return redirect("properties:payment_redirect", slug=slug)
            return redirect("properties:list")

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()
            conversation.save()  # bump updated_at

            # Notification is handled by dashboard views (client_conversation_detail and owner_conversation_detail)
            # This generic view is not used for the main messaging flow
            return redirect("messaging:conversation_detail", pk=pk)
    else:
        form = MessageForm()

    # Mark messages from the other party as read
    conversation.messages.exclude(sender=request.user).update(is_read=True)

    is_owner = request.user == conversation.owner
    return render(
        request,
        "messaging/conversation_detail.html",
        {
            "conversation": conversation,
            "form": form,
            "active": "messages",
            "dash_role": "owner" if is_owner else "client",
        },
    )


@login_required
def request_visit(request, pk):
    """Client requests a visit for the property in this conversation"""
    conversation = get_object_or_404(Conversation, pk=pk)
    
    # Security: only buyer can request visit
    if request.user != conversation.buyer:
        django_messages.error(request, "Seul le client peut demander une visite.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    if request.method == "POST":
        form = VisitRequestForm(request.POST)
        if form.is_valid():
            visit_request = form.save(commit=False)
            visit_request.conversation = conversation
            visit_request.requester = request.user
            visit_request.save()
            
            # Create a message in the conversation about the visit request
            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                body=f"📅 Demande de visite : {visit_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}\n{visit_request.message}",
                message_type=Message.MessageType.VISIT_REQUEST,
                proposed_date=visit_request.proposed_date,
                visit_request=visit_request
            )
            
            # Notify owner
            Notification.objects.create(
                user=conversation.owner,
                title="📅 Nouvelle demande de visite",
                message=f"{request.user.get_full_name() or request.user.username} souhaite visiter « {conversation.property.title if conversation.property else 'votre bien'} » le {visit_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}.",
                notification_type="systeme",
                link=f"/messagerie/{pk}/",
            )
            
            django_messages.success(request, "Votre demande de visite a été envoyée au propriétaire.")
            return redirect("messaging:conversation_detail", pk=pk)
    else:
        form = VisitRequestForm()
    
    return render(request, "messaging/request_visit.html", {
        "conversation": conversation,
        "form": form,
        "dash_role": "client",
    })


@login_required
def accept_visit(request, pk, visit_id):
    """Owner accepts a visit request"""
    conversation = get_object_or_404(Conversation, pk=pk)
    visit_request = get_object_or_404(VisitRequest, pk=visit_id, conversation=conversation)
    
    # Security: only owner can accept
    if request.user != conversation.owner:
        django_messages.error(request, "Seul le propriétaire peut accepter une visite.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    visit_request.status = VisitRequest.Status.ACCEPTED
    visit_request.save()
    
    # Create message about acceptance
    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=f"✅ Votre demande de visite pour le {visit_request.proposed_date.strftime('%d/%m/%Y à %H:%M')} a été acceptée.",
        message_type=Message.MessageType.VISIT_ACCEPTED,
        proposed_date=visit_request.proposed_date
    )
    
    # Notify client
    Notification.objects.create(
        user=conversation.buyer,
        title="✅ Demande de visite acceptée",
        message=f"Le propriétaire a accepté votre visite pour « {conversation.property.title if conversation.property else 'le bien'} » le {visit_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}.",
        notification_type="systeme",
        link=f"/messagerie/{pk}/",
    )
    
    django_messages.success(request, "Vous avez accepté la demande de visite.")
    return redirect("messaging:conversation_detail", pk=pk)


@login_required
def refuse_visit(request, pk, visit_id):
    """Owner refuses a visit request"""
    conversation = get_object_or_404(Conversation, pk=pk)
    visit_request = get_object_or_404(VisitRequest, pk=visit_id, conversation=conversation)
    
    # Security: only owner can refuse
    if request.user != conversation.owner:
        django_messages.error(request, "Seul le propriétaire peut refuser une visite.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    visit_request.status = VisitRequest.Status.REFUSED
    visit_request.save()
    
    # Create message about refusal
    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=f"❌ Votre demande de visite pour le {visit_request.proposed_date.strftime('%d/%m/%Y à %H:%M')} a été refusée.",
        message_type=Message.MessageType.VISIT_REFUSED,
        proposed_date=visit_request.proposed_date
    )
    
    # Notify client
    Notification.objects.create(
        user=conversation.buyer,
        title="❌ Demande de visite refusée",
        message=f"Le propriétaire a refusé votre demande de visite pour « {conversation.property.title if conversation.property else 'le bien'} ».",
        notification_type="systeme",
        link=f"/messagerie/{pk}/",
    )
    
    django_messages.success(request, "Vous avez refusé la demande de visite.")
    return redirect("messaging:conversation_detail", pk=pk)


@login_required
def propose_visit(request, pk, visit_id):
    """Owner proposes a new date for a visit request"""
    conversation = get_object_or_404(Conversation, pk=pk)
    visit_request = get_object_or_404(VisitRequest, pk=visit_id, conversation=conversation)
    
    # Security: only owner can propose new date
    if request.user != conversation.owner:
        django_messages.error(request, "Seul le propriétaire peut proposer une nouvelle date.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    if request.method == "POST":
        form = VisitResponseForm(request.POST)
        if form.is_valid():
            new_date = form.cleaned_data.get("proposed_date")
            response_message = form.cleaned_data.get("response_message", "")
            
            if new_date:
                visit_request.status = VisitRequest.Status.PROPOSED
                visit_request.response_message = response_message
                visit_request.save()
                
                # Create message about new proposal
                message_body = f"📅 Nouvelle proposition : {new_date.strftime('%d/%m/%Y à %H:%M')}"
                if response_message:
                    message_body += f"\n{response_message}"
                
                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    body=message_body,
                    message_type=Message.MessageType.VISIT_PROPOSED,
                    proposed_date=new_date
                )
                
                # Notify client
                Notification.objects.create(
                    user=conversation.buyer,
                    title="📅 Nouvelle date proposée",
                    message=f"Le propriétaire a proposé une nouvelle date pour la visite de « {conversation.property.title if conversation.property else 'le bien'} » : {new_date.strftime('%d/%m/%Y à %H:%M')}.",
                    notification_type="systeme",
                    link=f"/messagerie/{pk}/",
                )
                
                django_messages.success(request, "Votre nouvelle proposition a été envoyée.")
                return redirect("messaging:conversation_detail", pk=pk)
            else:
                django_messages.error(request, "Veuillez sélectionner une nouvelle date.")
    else:
        form = VisitResponseForm()
    
    return render(request, "messaging/propose_visit.html", {
        "conversation": conversation,
        "visit_request": visit_request,
        "form": form,
        "dash_role": "owner",
    })


@login_required
def request_rendezvous(request, pk):
    """Client requests a rendezvous with the owner"""
    conversation = get_object_or_404(Conversation, pk=pk, buyer=request.user)
    
    # Security: only buyer can request rendezvous
    if request.user != conversation.buyer:
        django_messages.error(request, "Seul l'acheteur peut demander un rendez-vous.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    if request.method == "POST":
        form = RendezvousRequestForm(request.POST)
        if form.is_valid():
            rendezvous_request = form.save(commit=False)
            rendezvous_request.conversation = conversation
            rendezvous_request.requester = request.user
            rendezvous_request.save()
            
            # Create message about rendezvous request
            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                body=f"🤝 Demande de rendez-vous : {rendezvous_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}\n{rendezvous_request.message}",
                message_type=Message.MessageType.RENDEZVOUS_REQUEST,
                proposed_date=rendezvous_request.proposed_date,
                rendezvous_request=rendezvous_request
            )
            
            # Notify owner
            Notification.objects.create(
                user=conversation.owner,
                title="🤝 Nouvelle demande de rendez-vous",
                message=f"{request.user.get_full_name() or request.user.username} souhaite prendre rendez-vous pour « {conversation.property.title if conversation.property else 'votre bien'} » le {rendezvous_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}.",
                notification_type="systeme",
                link=f"/messagerie/{pk}/",
            )
            
            django_messages.success(request, "Votre demande de rendez-vous a été envoyée au propriétaire.")
            return redirect("messaging:conversation_detail", pk=pk)
    else:
        form = RendezvousRequestForm()
    
    return render(request, "messaging/request_rendezvous.html", {
        "conversation": conversation,
        "form": form,
        "dash_role": "client",
    })


@login_required
def accept_rendezvous(request, pk, rendezvous_id):
    """Owner accepts a rendezvous request"""
    conversation = get_object_or_404(Conversation, pk=pk)
    rendezvous_request = get_object_or_404(RendezvousRequest, pk=rendezvous_id, conversation=conversation)
    
    # Security: only owner can accept
    if request.user != conversation.owner:
        django_messages.error(request, "Seul le propriétaire peut accepter un rendez-vous.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    rendezvous_request.status = RendezvousRequest.Status.ACCEPTED
    rendezvous_request.save()
    
    # Create message about acceptance
    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=f"✅ Votre demande de rendez-vous pour le {rendezvous_request.proposed_date.strftime('%d/%m/%Y à %H:%M')} a été acceptée.",
        message_type=Message.MessageType.RENDEZVOUS_ACCEPTED,
        proposed_date=rendezvous_request.proposed_date
    )
    
    # Notify client
    Notification.objects.create(
        user=conversation.buyer,
        title="✅ Demande de rendez-vous acceptée",
        message=f"Le propriétaire a accepté votre rendez-vous pour « {conversation.property.title if conversation.property else 'le bien'} » le {rendezvous_request.proposed_date.strftime('%d/%m/%Y à %H:%M')}.",
        notification_type="systeme",
        link=f"/messagerie/{pk}/",
    )
    
    django_messages.success(request, "Vous avez accepté la demande de rendez-vous.")
    return redirect("messaging:conversation_detail", pk=pk)


@login_required
def refuse_rendezvous(request, pk, rendezvous_id):
    """Owner refuses a rendezvous request"""
    conversation = get_object_or_404(Conversation, pk=pk)
    rendezvous_request = get_object_or_404(RendezvousRequest, pk=rendezvous_id, conversation=conversation)
    
    # Security: only owner can refuse
    if request.user != conversation.owner:
        django_messages.error(request, "Seul le propriétaire peut refuser un rendez-vous.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    rendezvous_request.status = RendezvousRequest.Status.REFUSED
    rendezvous_request.save()
    
    # Create message about refusal
    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=f"❌ Votre demande de rendez-vous pour le {rendezvous_request.proposed_date.strftime('%d/%m/%Y à %H:%M')} a été refusée.",
        message_type=Message.MessageType.RENDEZVOUS_REFUSED,
        proposed_date=rendezvous_request.proposed_date
    )
    
    # Notify client
    Notification.objects.create(
        user=conversation.buyer,
        title="❌ Demande de rendez-vous refusée",
        message=f"Le propriétaire a refusé votre rendez-vous pour « {conversation.property.title if conversation.property else 'le bien'} ».",
        notification_type="systeme",
        link=f"/messagerie/{pk}/",
    )
    
    django_messages.success(request, "Vous avez refusé la demande de rendez-vous.")
    return redirect("messaging:conversation_detail", pk=pk)


@login_required
def propose_rendezvous(request, pk, rendezvous_id):
    """Owner proposes a new date for a rendezvous"""
    conversation = get_object_or_404(Conversation, pk=pk)
    rendezvous_request = get_object_or_404(RendezvousRequest, pk=rendezvous_id, conversation=conversation)
    
    # Security: only owner can propose new date
    if request.user != conversation.owner:
        django_messages.error(request, "Seul le propriétaire peut proposer une nouvelle date.")
        return redirect("messaging:conversation_detail", pk=pk)
    
    if request.method == "POST":
        form = RendezvousResponseForm(request.POST)
        if form.is_valid():
            new_date = form.cleaned_data.get("proposed_date")
            response_message = form.cleaned_data.get("response_message", "")
            
            if new_date:
                rendezvous_request.status = RendezvousRequest.Status.PROPOSED
                rendezvous_request.response_message = response_message
                rendezvous_request.save()
                
                # Create message about new proposal
                message_body = f"📅 Nouvelle proposition : {new_date.strftime('%d/%m/%Y à %H:%M')}"
                if response_message:
                    message_body += f"\n{response_message}"
                
                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    body=message_body,
                    message_type=Message.MessageType.RENDEZVOUS_PROPOSED,
                    proposed_date=new_date
                )
                
                # Notify client
                Notification.objects.create(
                    user=conversation.buyer,
                    title="📅 Nouvelle date proposée",
                    message=f"Le propriétaire a proposé une nouvelle date pour le rendez-vous de « {conversation.property.title if conversation.property else 'le bien'} » : {new_date.strftime('%d/%m/%Y à %H:%M')}.",
                    notification_type="systeme",
                    link=f"/messagerie/{pk}/",
                )
                
                django_messages.success(request, "Votre nouvelle proposition a été envoyée.")
                return redirect("messaging:conversation_detail", pk=pk)
            else:
                django_messages.error(request, "Veuillez sélectionner une nouvelle date.")
    else:
        form = RendezvousResponseForm()
    
    return render(request, "messaging/propose_rendezvous.html", {
        "conversation": conversation,
        "rendezvous_request": rendezvous_request,
        "form": form,
        "dash_role": "owner",
    })
