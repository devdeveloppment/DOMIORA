from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages

from .models import Conversation, Message
from .forms import MessageForm
from agents.models import Agent
from properties.models import Property
from notifications.models import Notification


@login_required
def start_conversation(request, agent_id):
    agent = get_object_or_404(Agent, pk=agent_id)
    property_id = request.POST.get("property_id") or request.GET.get("property")
    property_obj = Property.objects.filter(pk=property_id).first() if property_id else None
    initial_message = request.POST.get("message", "").strip()

    conversation, _ = Conversation.objects.get_or_create(
        buyer=request.user, agent=agent, property=property_obj,
    )
    if initial_message:
        Message.objects.create(conversation=conversation, sender=request.user, body=initial_message)
        Notification.objects.create(
            user=agent.user, title="Nouveau message",
            message=f"{request.user.get_full_name()} vous a envoyé un message.",
            notification_type="systeme", link="/dashboard/agent/messagerie/",
        )
    return redirect("messaging:conversation_detail", pk=conversation.pk)


@login_required
def inbox(request):
    agent = Agent.objects.filter(user=request.user).first()
    if agent:
        conversations = list(Conversation.objects.filter(agent=agent).select_related("buyer", "property"))
        role = "agent"
    else:
        conversations = list(Conversation.objects.filter(buyer=request.user).select_related("agent__user", "property"))
        role = "buyer"
    for c in conversations:
        c.unread = c.unread_count_for(request.user)
    return render(request, "messaging/inbox.html", {"conversations": conversations, "dash_role": role, "active": "messages"})


@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    if request.user not in (conversation.buyer, conversation.agent.user):
        return redirect("messaging:inbox")

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()
            conversation.save()  # bump updated_at (auto_now)
            recipient = conversation.agent.user if request.user == conversation.buyer else conversation.buyer
            Notification.objects.create(
                user=recipient, title="Nouveau message", message=msg.body[:120],
                notification_type="systeme",
            )
            return redirect("messaging:conversation_detail", pk=pk)
    else:
        form = MessageForm()

    conversation.messages.exclude(sender=request.user).update(is_read=True)
    is_agent = Agent.objects.filter(user=request.user).exists()
    return render(request, "messaging/conversation_detail.html", {
        "conversation": conversation, "form": form,
        "dash_role": "agent" if is_agent else "buyer", "active": "messages",
    })
