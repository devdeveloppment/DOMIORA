from django.db import models
from django.conf import settings


class Conversation(models.Model):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_buyer")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_owner")
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("buyer", "owner", "property")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.buyer} ↔ {self.owner}"

    def last_message(self):
        return self.messages.order_by("-created_at").first()

    def unread_count_for(self, user):
        return self.messages.exclude(sender=user).filter(is_read=False).count()


class Message(models.Model):
    class MessageType(models.TextChoices):
        TEXT = "text", "Message texte"
        VISIT_REQUEST = "visit_request", "Demande de visite"
        VISIT_ACCEPTED = "visit_accepted", "Visite acceptée"
        VISIT_REFUSED = "visit_refused", "Visite refusée"
        VISIT_PROPOSED = "visit_proposed", "Nouvelle date proposée"
        RENDEZVOUS_REQUEST = "rendezvous_request", "Demande de rendez-vous"
        RENDEZVOUS_ACCEPTED = "rendezvous_accepted", "Rendez-vous accepté"
        RENDEZVOUS_REFUSED = "rendezvous_refused", "Rendez-vous refusé"
        RENDEZVOUS_PROPOSED = "rendezvous_proposed", "Nouvelle date proposée"
        INFO = "info", "Information"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    message_type = models.CharField(max_length=25, choices=MessageType.choices, default=MessageType.TEXT)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Visit request specific fields
    visit_request = models.ForeignKey('VisitRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name="messages", help_text="Related visit request if this message is about a visit")
    rendezvous_request = models.ForeignKey('RendezvousRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name="messages", help_text="Related rendezvous request if this message is about a rendezvous")
    proposed_date = models.DateTimeField(null=True, blank=True, help_text="Proposed date for visit or rendezvous")
    visit_status = models.CharField(max_length=20, blank=True, help_text="Status of visit request")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.body[:30]}"


class VisitRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Acceptée"
        REFUSED = "refused", "Refusée"
        PROPOSED = "proposed", "Nouvelle date proposée"
        CANCELLED = "cancelled", "Annulée"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="visit_requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_visit_requests")
    proposed_date = models.DateTimeField()
    message = models.TextField(help_text="Additional message from requester")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    response_message = models.TextField(blank=True, help_text="Owner's response message")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Visit request for {self.conversation.property.title if self.conversation.property else 'Unknown'} - {self.status}"


class RendezvousRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Accepté"
        REFUSED = "refused", "Refusé"
        PROPOSED = "proposed", "Nouvelle date proposée"
        CANCELLED = "cancelled", "Annulé"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="rendezvous_requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_rendezvous_requests")
    proposed_date = models.DateTimeField()
    message = models.TextField(help_text="Additional message from requester")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    response_message = models.TextField(blank=True, help_text="Owner's response message")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rendezvous request for {self.conversation.property.title if self.conversation.property else 'Unknown'} - {self.status}"
