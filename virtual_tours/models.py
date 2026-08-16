from django.db import models
from django.conf import settings
from django.utils import timezone


class VirtualTourSession(models.Model):
    """WebRTC session for live virtual tours"""
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Programmée"
        IN_PROGRESS = "in_progress", "En cours"
        COMPLETED = "completed", "Terminée"
        CANCELLED = "cancelled", "Annulée"
    
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='virtual_tours')
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_tours')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='attended_tours')
    
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    
    # WebRTC signaling
    session_id = models.CharField(max_length=100, unique=True, blank=True)
    agent_signal_data = models.JSONField(default=dict, blank=True)
    buyer_signal_data = models.JSONField(default=dict, blank=True)
    
    # Features enabled
    screen_sharing_enabled = models.BooleanField(default=False)
    audio_enabled = models.BooleanField(default=True)
    video_enabled = models.BooleanField(default=True)
    chat_enabled = models.BooleanField(default=True)
    
    # Recording
    is_recorded = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True)
    
    notes = models.TextField(blank=True, help_text="Notes de la visite virtuelle")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_at']
        indexes = [
            models.Index(fields=['property', 'status']),
            models.Index(fields=['agent', 'scheduled_at']),
            models.Index(fields=['buyer', 'scheduled_at']),
        ]
    
    def __str__(self):
        return f"Visite virtuelle - {self.property.title} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.session_id:
            import uuid
            self.session_id = str(uuid.uuid4())
        super().save(*args, **kwargs)


class TourChatMessage(models.Model):
    """Chat messages during virtual tour"""
    session = models.ForeignKey(VirtualTourSession, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.sender.username}: {self.message[:50]}"
