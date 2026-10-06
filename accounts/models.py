# Modèles pour la gestion des utilisateurs et de l'authentification dans DOMIORA
# Ce fichier définit le modèle User personnalisé et le système de vérification d'identité

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.db.models import Avg


class User(AbstractUser):
    """
    Modèle utilisateur personnalisé étendant AbstractUser de Django
    Supporte trois rôles principaux : client, propriétaire, administrateur
    """

    class Role(models.TextChoices):
        """Rôles disponibles dans le système"""
        CLIENT = "client", "Client"  # Acheteur ou locataire
        OWNER = "owner", "Propriétaire"  # Propriétaire de biens immobiliers
        ADMIN = "admin", "Administrateur"  # Administrateur système

    # Champs de base hérités d'AbstractUser : username, email, first_name, last_name, password, etc.
    
    # Champs personnalisés pour DOMIORA
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)  # Rôle de l'utilisateur
    phone = models.CharField(max_length=30, blank=True)  # Numéro de téléphone
    whatsapp_number = models.CharField(max_length=30, blank=True)  # Numéro WhatsApp
    agency_name = models.CharField(max_length=100, blank=True)  # Nom de l'agence (pour agents)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)  # Photo de profil
    bio = models.TextField(blank=True)  # Biographie
    is_suspended = models.BooleanField(default=False, help_text="Compte désactivé par un administrateur")  # Suspension du compte
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création du compte
    
    # Système de vérification d'identité pour les propriétaires
    class VerificationStatus(models.TextChoices):
        """Statuts de vérification d'identité"""
        UNVERIFIED = "unverified", "Non vérifié"
        PENDING_DOCUMENTS = "pending_documents", "Documents en cours d'analyse"
        PENDING_FIELD_VISIT = "pending_field_visit", "Vérification terrain programmée"
        FIELD_VISIT_COMPLETED = "field_visit_completed", "Vérification terrain effectuée"
        APPROVED = "approved", "Identité vérifiée"
        REJECTED = "rejected", "Identité rejetée"
        
    verification_status = models.CharField(max_length=30, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED)  # Statut de vérification
    can_publish_properties = models.BooleanField(default=False, help_text="Autorisé à publier des propriétés après vérification")  # Droit de publication
    id_document = models.ImageField(upload_to="id_documents/", blank=True, null=True)  # Pièce d'identité
    id_document_type = models.CharField(max_length=50, blank=True)  # Type de pièce d'identité
    id_document_number = models.CharField(max_length=50, blank=True)  # Numéro de pièce d'identité
    verification_date = models.DateTimeField(null=True, blank=True)  # Date de vérification
    verification_rejection_reason = models.TextField(blank=True)  # Motif de rejet
    
    # Champs pour la vérification sur place (field visit)
    field_visit_scheduled = models.DateTimeField(null=True, blank=True, verbose_name="Date de visite programmée")  # Date de visite terrain
    field_visit_completed = models.DateTimeField(null=True, blank=True, verbose_name="Date de visite effectuée")  # Date de visite effectuée
    field_visit_agent = models.CharField(max_length=100, blank=True, verbose_name="Agent de visite")  # Nom de l'agent de visite
    field_visit_notes = models.TextField(blank=True, verbose_name="Notes de visite")  # Notes de la visite
    property_verified = models.BooleanField(default=False, verbose_name="Bien vérifié sur place")  # Vérification du bien
    property_verification_notes = models.TextField(blank=True, verbose_name="Notes de vérification du bien")  # Notes de vérification

    class Meta:
        ordering = ["-date_joined"]  # Tri par date d'inscription décroissante
        indexes = [
            models.Index(fields=["role"]),  # Index sur le rôle pour optimiser les filtres
            models.Index(fields=["email"]),  # Index sur l'email pour la recherche
            models.Index(fields=["verification_status"]),  # Index sur le statut de vérification
            models.Index(fields=["is_suspended"]),  # Index sur le statut de suspension
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_client(self):
        """Vérifie si l'utilisateur est un client"""
        return self.role == self.Role.CLIENT

    @property
    def is_owner(self):
        """Vérifie si l'utilisateur est un propriétaire"""
        return self.role == self.Role.OWNER

    @property
    def is_admin_role(self):
        """Vérifie si l'utilisateur est un administrateur"""
        return self.role == self.Role.ADMIN or self.is_superuser

    def get_absolute_url(self):
        """Retourne l'URL du profil utilisateur"""
        return reverse("accounts:profile")

    def get_avatar_url(self):
        """Retourne l'URL de l'avatar ou une image par défaut"""
        if self.avatar:
            return self.avatar.url
        if self.role == self.Role.ADMIN or self.is_superuser:
            return "/media/settings/ChatGPT_Image_26_août_2026_14_32_40.png"
        return "https://ui-avatars.com/api/?background=7c3aed&color=fff&name=" + (self.get_full_name() or self.username).replace(" ", "+")

    @property
    def is_verified_owner(self):
        """Vérifie si le propriétaire est vérifié"""
        return self.verification_status == self.VerificationStatus.APPROVED

    @property
    def average_rating(self):
        """Calcule la note moyenne basée sur les avis clients"""
        from ratings.models import Review
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(avg=Avg('rating'))['avg']
        return None

    @property
    def reviews_count(self):
        """Compte le nombre d'avis approuvés"""
        from ratings.models import Review
        return self.reviews.filter(is_approved=True).count()

    @property
    def get_published_properties_count(self):
        """Compte le nombre de propriétés publiées"""
        from properties.models import Property
        return Property.objects.filter(owner=self, is_published=True).count()

    @property
    def average_response_display(self):
        """Affiche le temps de réponse moyen (placeholder)"""
        return "< 30 minutes"  # Placeholder, pourrait être calculé à partir des données réelles

    @property
    def verification_badge_html(self):
        """Retourne le HTML du badge de vérification"""
        if self.is_verified_owner:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700">✅ Propriétaire vérifié</span>'
        elif self.verification_status == self.VerificationStatus.PENDING_DOCUMENTS:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-amber-100 text-amber-700">⚪ Documents en cours d\'analyse</span>'
        elif self.verification_status == self.VerificationStatus.PENDING_FIELD_VISIT:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-blue-100 text-blue-700">📍 Vérification terrain programmée</span>'
        elif self.verification_status == self.VerificationStatus.FIELD_VISIT_COMPLETED:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-purple-100 text-purple-700">🔍 Vérification terrain effectuée</span>'
        elif self.verification_status == self.VerificationStatus.REJECTED:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-red-100 text-red-700">❌ Identité rejetée</span>'
        return ''

    def get_published_properties_count(self):
        """Compte le nombre de propriétés publiées"""
        return self.properties.filter(is_published=True).count()

    def get_active_properties_count(self):
        """Compte le nombre de propriétés actives (disponibles)"""
        return self.properties.filter(is_published=True, status='disponible').count()

    def get_total_views_count(self):
        """Compte le total des vues sur toutes les propriétés"""
        from django.db.models import Sum
        result = self.properties.aggregate(total=Sum('views_count'))['total']
        return result or 0

    def get_total_favorites_count(self):
        """Compte le total des favoris sur toutes les propriétés"""
        from favorites.models import Favorite
        return Favorite.objects.filter(property__owner=self).count()

    @property
    def properties_count(self):
        """Compte le nombre total de propriétés"""
        return self.properties.count()

    @property
    def active_properties_count(self):
        """Compte le nombre de propriétés actives"""
        return self.properties.filter(is_published=True, status="disponible").count()

    @property
    def verified_properties_count(self):
        """Compte le nombre de propriétés vérifiées"""
        return self.properties.filter(is_validated=True).count()

    @property
    def pending_properties_count(self):
        """Compte le nombre de propriétés en attente de validation"""
        from properties.models import Property
        return self.properties.filter(validation_status=Property.ValidationStatus.PENDING).count()

    @property
    def rejected_properties_count(self):
        """Compte le nombre de propriétés rejetées"""
        from properties.models import Property
        return self.properties.filter(validation_status=Property.ValidationStatus.REJECTED).count()

    @property
    def response_rate(self):
        """Calcule le taux de réponse aux demandes"""
        from rental_requests.models import PropertyRequest

        requests = PropertyRequest.objects.filter(property__owner=self)
        total = requests.count()
        if not total:
            return 0
        answered = requests.filter(status__in=[PropertyRequest.Status.ACCEPTEE, PropertyRequest.Status.REJETEE]).count()
        return round((answered / total) * 100)

    @property
    def average_response_minutes(self):
        """Calcule le temps de réponse moyen en minutes"""
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
        """Formate le temps de réponse pour l'affichage"""
        minutes = self.average_response_minutes
        if minutes is None:
            return "Réponse à venir"
        if minutes < 60:
            return f"{minutes} min"
        hours = round(minutes / 60)
        return f"{hours} h"


class IdentityVerificationRequest(models.Model):
    """
    Modèle pour les demandes de vérification d'identité des propriétaires
    Gère le processus complet de vérification : documents, visite terrain, validation
    """
    
    class Status(models.TextChoices):
        """Statuts possibles d'une demande de vérification"""
        PENDING = "pending", "En attente de documents"
        DOCUMENTS_UNDER_REVIEW = "documents_under_review", "Documents en cours d'analyse"
        FIELD_VISIT_SCHEDULED = "field_visit_scheduled", "Vérification terrain programmée"
        FIELD_VISIT_COMPLETED = "field_visit_completed", "Vérification terrain effectuée"
        APPROVED = "approved", "Validé"
        REJECTED = "rejected", "Refusé"
        RESUBMISSION_REQUESTED = "resubmission_requested", "Nouvelle soumission demandée"
    
    # Relation avec le propriétaire
    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="verification_requests",
        limit_choices_to={"role": User.Role.OWNER}
    )
    
    # Documents d'identité
    id_document_front = models.ImageField(upload_to="id_documents/front/", verbose_name="Recto de la pièce d'identité")  # Recto de la pièce d'identité
    id_document_back = models.ImageField(upload_to="id_documents/back/", verbose_name="Verso de la pièce d'identité")  # Verso de la pièce d'identité
    
    # Informations sur le document
    id_document_type = models.CharField(max_length=50, blank=True, verbose_name="Type de pièce d'identité")  # Type (CNI, passeport, etc.)
    id_document_number = models.CharField(max_length=50, blank=True, verbose_name="Numéro de la pièce d'identité")  # Numéro du document
    
    # Suivi du statut
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Statut de la demande"
    )  # Statut actuel de la demande
    
    # Motif de rejet
    rejection_reason = models.TextField(blank=True, verbose_name="Motif du refus")  # Raison du rejet si applicable
    
    # Horodatage
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de soumission")  # Date de soumission
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de révision")  # Date de révision par l'admin
    reviewed_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_verifications",
        limit_choices_to={"role": User.Role.ADMIN}
    )  # Administrateur qui a révisé la demande
    
    # Intégration n8n (automatisation)
    n8n_resume_url = models.URLField(blank=True, null=True, verbose_name="URL de reprise n8n")  # URL pour reprendre le workflow n8n
    n8n_execution_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID d'exécution n8n")  # ID d'exécution du workflow
    
    # Champs pour la vérification sur place
    field_visit_scheduled = models.DateTimeField(null=True, blank=True, verbose_name="Date de visite programmée")  # Date de visite terrain
    field_visit_completed = models.DateTimeField(null=True, blank=True, verbose_name="Date de visite effectuée")  # Date de visite effectuée
    field_visit_agent = models.CharField(max_length=100, blank=True, verbose_name="Agent de visite")  # Nom de l'agent de visite
    field_visit_notes = models.TextField(blank=True, verbose_name="Notes de visite")  # Notes de la visite
    property_verified = models.BooleanField(default=False, verbose_name="Bien vérifié sur place")  # Résultat de la vérification
    property_verification_notes = models.TextField(blank=True, verbose_name="Notes de vérification du bien")  # Notes sur le bien
    
    class Meta:
        ordering = ["-submitted_at"]  # Tri par date de soumission décroissante
        verbose_name = "Demande de vérification d'identité"
        verbose_name_plural = "Demandes de vérification d'identité"
    
    def __str__(self):
        return f"Vérification #{self.id} - {self.owner.get_full_name() or self.owner.username}"
    
    @property
    def is_approved(self):
        """Vérifie si la demande est approuvée"""
        return self.status == self.Status.APPROVED
    
    @property
    def is_pending(self):
        """Vérifie si la demande est en attente"""
        return self.status == self.Status.PENDING
    
    @property
    def is_rejected(self):
        """Vérifie si la demande est rejetée"""
        return self.status == self.Status.REJECTED
    
    @property
    def needs_resubmission(self):
        """Vérifie si une nouvelle soumission est demandée"""
        return self.status == self.Status.RESUBMISSION_REQUESTED
    
    def approve(self, admin_user):
        """Approuve la demande de vérification"""
        self.status = self.Status.APPROVED
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Mise à jour du statut du propriétaire
        self.owner.verification_status = self.owner.VerificationStatus.APPROVED
        self.owner.can_publish_properties = True
        self.owner.verification_date = timezone.now()
        self.owner.verification_rejection_reason = ""
        self.owner.save(update_fields=["verification_status", "can_publish_properties", "verification_date", "verification_rejection_reason"])
    
    def reject(self, admin_user, reason):
        """Rejette la demande de vérification"""
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Mise à jour du statut du propriétaire
        self.owner.verification_status = self.owner.VerificationStatus.REJECTED
        self.owner.can_publish_properties = False
        self.owner.verification_rejection_reason = reason
        self.owner.save(update_fields=["verification_status", "can_publish_properties", "verification_rejection_reason"])
    
    def request_resubmission(self, admin_user, reason):
        """Demande une nouvelle soumission de documents"""
        self.status = self.Status.RESUBMISSION_REQUESTED
        self.rejection_reason = reason
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Mise à jour du statut du propriétaire
        self.owner.verification_status = self.owner.VerificationStatus.PENDING_DOCUMENTS
        self.owner.verification_rejection_reason = reason
        self.owner.save(update_fields=["verification_status", "verification_rejection_reason"])
    
    def schedule_field_visit(self, admin_user, scheduled_date, agent_name):
        """Programme une visite sur place pour vérification"""
        self.status = self.Status.FIELD_VISIT_SCHEDULED
        self.field_visit_scheduled = scheduled_date
        self.field_visit_agent = agent_name
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Mise à jour du statut du propriétaire
        self.owner.verification_status = self.owner.VerificationStatus.PENDING_FIELD_VISIT
        self.owner.field_visit_scheduled = scheduled_date
        self.owner.field_visit_agent = agent_name
        self.owner.save(update_fields=["verification_status", "field_visit_scheduled", "field_visit_agent"])
    
    def complete_field_visit(self, admin_user, notes, property_verified=False, property_notes=""):
        """Complète la visite sur place et enregistre les résultats"""
        self.status = self.Status.FIELD_VISIT_COMPLETED
        self.field_visit_completed = timezone.now()
        self.field_visit_notes = notes
        self.property_verified = property_verified
        self.property_verification_notes = property_notes
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
        
        # Mise à jour du statut du propriétaire
        self.owner.verification_status = self.owner.VerificationStatus.FIELD_VISIT_COMPLETED
        self.owner.field_visit_completed = timezone.now()
        self.owner.field_visit_notes = notes
        self.owner.property_verified = property_verified
        self.owner.property_verification_notes = property_notes
        self.owner.save(update_fields=["verification_status", "field_visit_completed", "field_visit_notes", "property_verified", "property_verification_notes"])
