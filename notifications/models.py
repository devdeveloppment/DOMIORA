from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotifType(models.TextChoices):
        INFO = "info", "Info"
        DEMANDE = "demande", "Nouvelle demande"
        TRANSACTION = "transaction", "Transaction"
        SYSTEME = "systeme", "Système"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    notification_type = models.CharField(max_length=12, choices=NotifType.choices, default=NotifType.INFO)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
