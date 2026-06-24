from django.db import models
from django.conf import settings


class Conversation(models.Model):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_buyer")
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="conversations")
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("buyer", "agent", "property")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.buyer} ↔ {self.agent}"

    def last_message(self):
        return self.messages.order_by("-created_at").first()

    def unread_count_for(self, user):
        return self.messages.exclude(sender=user).filter(is_read=False).count()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.body[:30]}"
