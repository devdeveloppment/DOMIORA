# Modèles pour la gestion des agents immobiliers dans DOMIORA
# Ce fichier définit la structure de la base de données pour les agents, leurs spécialités et les avis clients

from django.db import models
from django.urls import reverse
from django.conf import settings


class Specialty(models.Model):
    """
    Modèle représentant les spécialités des agents immobiliers
    Ex: Résidentiel, Commercial, Luxe, Location, etc.
    """
    name = models.CharField(max_length=60, unique=True)  # Nom de la spécialité (unique)

    class Meta:
        verbose_name_plural = "Specialties"  # Nom pluriel pour l'interface admin
        ordering = ["name"]  # Tri alphabétique par nom

    def __str__(self):
        return self.name


class Agent(models.Model):
    """
    Modèle principal pour les profils d'agents immobiliers
    Chaque agent est lié à un utilisateur du système (relation One-to-One)
    """
    # Relation avec l'utilisateur du système
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_profile")
    
    # Informations professionnelles
    agency_name = models.CharField(max_length=150, blank=True)  # Nom de l'agence immobilière
    license_number = models.CharField(max_length=60, blank=True, verbose_name="N° de licence")  # Numéro de licence professionnelle
    bio = models.TextField(blank=True)  # Biographie/description de l'agent
    
    # Informations financières et expérience
    commission_rate = models.DecimalField(max_digits=4, decimal_places=1, default=5.0, help_text="En %")  # Taux de commission (en pourcentage)
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, default=0)  # Années d'expérience
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)  # Note moyenne (sur 5)
    is_verified = models.BooleanField(default=False)  # Statut de vérification de l'agent
    
    # Spécialités et réseaux sociaux
    specialties = models.ManyToManyField(Specialty, blank=True, related_name="agents")  # Spécialités de l'agent (relation many-to-many)
    facebook = models.URLField(blank=True)  # Lien Facebook
    instagram = models.URLField(blank=True)  # Lien Instagram
    linkedin = models.URLField(blank=True)  # Lien LinkedIn
    twitter = models.URLField(blank=True)  # Lien Twitter
    youtube = models.URLField(blank=True)  # Lien YouTube
    
    # Performance et disponibilité
    response_time_hours = models.PositiveIntegerField(default=24)  # Temps de réponse moyen en heures
    
    # Horodatage
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création du profil

    class Meta:
        ordering = ["-created_at"]  # Tri par date de création décroissante

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def get_absolute_url(self):
        return reverse("agents:detail", kwargs={"pk": self.pk})

    @property
    def active_properties_count(self):
        """Compte le nombre de propriétés actives (publiées et non vendues/louées)"""
        from properties.models import Property
        return Property.objects.filter(owner=self.user, is_published=True).exclude(status="vendu").exclude(status="loue").count()

    @property
    def sold_or_rented_count(self):
        """Compte le nombre de propriétés vendues ou louées"""
        from properties.models import Property
        return Property.objects.filter(owner=self.user, status__in=["vendu", "loue"]).count()

    @property
    def total_properties_count(self):
        """Compte le nombre total de propriétés de l'agent"""
        from properties.models import Property
        return Property.objects.filter(owner=self.user).count()

    @property
    def average_rating(self):
        """Calcule la note moyenne basée sur les avis clients"""
        agg = self.reviews.aggregate(avg=models.Avg("rating"))["avg"]
        return round(agg, 1) if agg else self.rating

    @property
    def review_count(self):
        """Compte le nombre d'avis reçus"""
        return self.reviews.count()

    @property
    def is_top_agent(self):
        """Détermine si l'agent est un top agent (note >= 4.7 et au moins 3 ventes/locations)"""
        return self.average_rating >= 4.7 and self.sold_or_rented_count >= 3


class AgentReview(models.Model):
    """
    Modèle pour les avis clients sur les agents immobiliers
    Chaque utilisateur ne peut laisser qu'un seul avis par agent
    """
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="reviews")  # Agent concerné
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_reviews")  # Utilisateur qui laisse l'avis
    rating = models.PositiveSmallIntegerField(default=5)  # Note de 1 à 5
    comment = models.TextField(blank=True)  # Commentaire détaillé
    created_at = models.DateTimeField(auto_now_add=True)  # Date de l'avis

    class Meta:
        unique_together = ("agent", "user")  # Un utilisateur ne peut laisser qu'un avis par agent
        ordering = ["-created_at"]  # Tri par date décroissante

    def __str__(self):
        return f"{self.user} → {self.agent} ({self.rating}★)"
