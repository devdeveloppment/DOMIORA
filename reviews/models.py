from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Review(models.Model):
    """Reviews/avis pour les propriétaires"""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_reviews')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200, help_text="Titre court de l'avis")
    comment = models.TextField(help_text="Détaillé de votre expérience")
    
    # Categories of rating
    communication_rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, help_text="Communication")
    professionalism_rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, help_text="Professionnalisme")
    responsiveness_rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, help_text="Réactivité")
    
    is_verified = models.BooleanField(default=False, help_text="Transaction vérifiée")
    is_approved = models.BooleanField(default=False, help_text="Approuvé par admin")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['owner', 'reviewer']
        indexes = [
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['rating']),
            models.Index(fields=['is_approved']),
        ]
    
    def __str__(self):
        return f"{self.reviewer.get_full_name()} - {self.owner.get_full_name()} ({self.rating}/5)"
    
    @property
    def average_category_rating(self):
        """Calculate average of category ratings"""
        ratings = []
        if self.communication_rating:
            ratings.append(self.communication_rating)
        if self.professionalism_rating:
            ratings.append(self.professionalism_rating)
        if self.responsiveness_rating:
            ratings.append(self.responsiveness_rating)
        if ratings:
            return sum(ratings) / len(ratings)
        return None