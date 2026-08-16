from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone


class User(AbstractUser):
    """Custom user model supporting three roles: client, owner, admin."""

    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        BUYER = "buyer", "Acheteur"
        OWNER = "owner", "Propriétaire"
        AGENT = "agent", "Agent"
        ADMIN = "admin", "Administrateur"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp_number = models.CharField(max_length=30, blank=True)
    agency_name = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    is_suspended = models.BooleanField(default=False, help_text="Compte désactivé par un administrateur")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Non vérifié"
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvé"
        REJECTED = "rejected", "Refusé"
        
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED)
    can_publish_properties = models.BooleanField(default=False, help_text="Autorisé à publier des propriétés après vérification")
    id_document = models.ImageField(upload_to="id_documents/", blank=True, null=True)
    id_document_type = models.CharField(max_length=50, blank=True)
    id_document_number = models.CharField(max_length=50, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def get_absolute_url(self):
        return reverse("accounts:profile")

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return "https://ui-avatars.com/api/?background=7c3aed&color=fff&name=" + (self.get_full_name() or self.username).replace(" ", "+")

    @property
    def is_verified_owner(self):
        """Check if owner is verified"""
        return self.verification_status == self.VerificationStatus.APPROVED

    @property
    def verification_badge_html(self):
        """Return HTML for verification badge"""
        if self.is_verified_owner:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700">✅ Propriétaire vérifié</span>'
        elif self.verification_status == self.VerificationStatus.PENDING:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-amber-100 text-amber-700">⚪ Vérification en cours</span>'
        return ''

    def get_published_properties_count(self):
        """Count of published properties"""
        return self.properties.filter(is_published=True).count()

    def get_active_properties_count(self):
        """Count of active (available) properties"""
        return self.properties.filter(is_published=True, status='disponible').count()

    def get_total_views_count(self):
        """Total views across all properties"""
        from django.db.models import Sum
        result = self.properties.aggregate(total=Sum('views_count'))['total']
        return result or 0

    def get_total_favorites_count(self):
        """Total favorites across all properties"""
        from favorites.models import Favorite
        return Favorite.objects.filter(property__owner=self).count()

    @property
    def properties_count(self):
        return self.properties.count()

    @property
    def active_properties_count(self):
        return self.properties.filter(is_published=True, status="disponible").count()

    @property
    def verified_properties_count(self):
        return self.properties.filter(is_validated=True).count()

    @property
    def pending_properties_count(self):
        from properties.models import Property
        return self.properties.filter(validation_status=Property.ValidationStatus.PENDING).count()

    @property
    def rejected_properties_count(self):
        from properties.models import Property
        return self.properties.filter(validation_status=Property.ValidationStatus.REJECTED).count()

    @property
    def response_rate(self):
        from rental_requests.models import PropertyRequest

        requests = PropertyRequest.objects.filter(property__owner=self)
        total = requests.count()
        if not total:
            return 0
        answered = requests.filter(status__in=[PropertyRequest.Status.ACCEPTEE, PropertyRequest.Status.REJETEE]).count()
        return round((answered / total) * 100)

    @property
    def average_response_minutes(self):
        from rental_requests.models import PropertyRequest

        answered = PropertyRequest.objects.filter(
            property__owner=self,
            status__in=[PropertyRequest.Status.ACCEPTEE, PropertyRequest.Status.REJETEE],
        )
        durations = []
        for item in answered.only("created_at", "updated_at"):
            delta = item.updated_at - item.created_at
            durations.append(max(int(delta.total_seconds() // 60), 0))
        if not durations:
            return None
        return round(sum(durations) / len(durations))

    @property
    def average_response_display(self):
        minutes = self.average_response_minutes
        if minutes is None:
            return "Réponse à venir"
        if minutes < 60:
            return f"{minutes} min"
        hours = round(minutes / 60)
        return f"{hours} h"


class IdentityVerificationRequest(models.Model):
    """Model for identity verification requests from property owners."""
    
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Validé"
        REJECTED = "rejected", "Refusé"
        RESUBMISSION_REQUESTED = "resubmission_requested", "Nouvelle soumission demandée"
    
    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="verification_requests",
        limit_choices_to={"role": User.Role.OWNER}
    )
    
    # Document images
    id_document_front = models.ImageField(upload_to="id_documents/front/", verbose_name="Recto de la pièce d'identité")
    id_document_back = models.ImageField(upload_to="id_documents/back/", verbose_name="Verso de la pièce d'identité")
    
    # Document info
    id_document_type = models.CharField(max_length=50, blank=True, verbose_name="Type de pièce d'identité")
    id_document_number = models.CharField(max_length=50, blank=True, verbose_name="Numéro de la pièce d'identité")
    
    # Status tracking
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Statut de la demande"
    )
    
    # Rejection reason
    rejection_reason = models.TextField(blank=True, verbose_name="Motif du refus")
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de soumission")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de révision")
    reviewed_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_verifications",
        limit_choices_to={"role": User.Role.ADMIN}
    )
    
    # n8n integration fields
    n8n_resume_url = models.URLField(blank=True, null=True, verbose_name="URL de reprise n8n")
    n8n_execution_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID d'exécution n8n")
    
    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Demande de vérification d'identité"
        verbose_name_plural = "Demandes de vérification d'identité"
    
    def __str__(self):
        return f"Vérification #{self.id} - {self.owner.get_full_name() or self.owner.username}"
    
    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED
    
    @property
    def is_pending(self):
        return self.status == self.Status.PENDING
    
    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED
    
    @property
    def needs_resubmission(self):
        return self.status == self.Status.RESUBMISSION_REQUESTED
    
    def approve(self, admin_user):
        """Approve the verification request."""
        self.status = self.Status.APPROVED
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Update owner's verification status
        self.owner.verification_status = self.owner.VerificationStatus.APPROVED
        self.owner.can_publish_properties = True
        self.owner.verification_date = timezone.now()
        self.owner.verification_rejection_reason = ""
        self.owner.save(update_fields=["verification_status", "can_publish_properties", "verification_date", "verification_rejection_reason"])
    
    def reject(self, admin_user, reason):
        """Reject the verification request."""
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Update owner's verification status
        self.owner.verification_status = self.owner.VerificationStatus.REJECTED
        self.owner.can_publish_properties = False
        self.owner.verification_rejection_reason = reason
        self.owner.save(update_fields=["verification_status", "can_publish_properties", "verification_rejection_reason"])
    
    def request_resubmission(self, admin_user, reason):
        """Request resubmission of documents."""
        self.status = self.Status.RESUBMISSION_REQUESTED
        self.rejection_reason = reason
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Update owner's verification status
        self.owner.verification_status = self.owner.VerificationStatus.PENDING
        self.owner.verification_rejection_reason = reason
        self.owner.save(update_fields=["verification_status", "verification_rejection_reason"])
