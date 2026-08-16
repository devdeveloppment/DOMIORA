from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class BoostPackage(models.Model):
    """Boost packages for property visibility"""
    class Duration(models.TextChoices):
        DAY_1 = "1_day", "1 jour"
        DAY_3 = "3_days", "3 jours"
        DAY_7 = "7_days", "7 jours"
        DAY_14 = "14_days", "14 jours"
        DAY_30 = "30_days", "30 jours"
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    duration = models.CharField(max_length=20, choices=Duration.choices)
    duration_days = models.PositiveSmallIntegerField(help_text="Duration in days")
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    
    # Boost multiplier (higher = more visibility)
    boost_multiplier = models.PositiveSmallIntegerField(default=2, help_text="Visibility multiplier (2x, 3x, etc.)")
    
    # Features
    featured_placement = models.BooleanField(default=False, help_text="Show in featured section")
    top_of_search = models.BooleanField(default=False, help_text="Show at top of search results")
    badge_highlight = models.BooleanField(default=False, help_text="Add special badge")
    priority_support = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['duration_days', 'price']
    
    def __str__(self):
        return f"{self.name} ({self.duration_days} jours) - {self.price} {self.currency}"


class PropertyBoost(models.Model):
    """Active boost for a property"""
    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        EXPIRED = "expired", "Expiré"
        CANCELLED = "cancelled", "Annulé"
        PENDING = "pending", "En attente"
    
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='boosts')
    package = models.ForeignKey(BoostPackage, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Timing
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Payment
    is_paid = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    views_before_boost = models.PositiveIntegerField(default=0)
    views_during_boost = models.PositiveIntegerField(default=0)
    inquiries_before_boost = models.PositiveIntegerField(default=0)
    inquiries_during_boost = models.PositiveIntegerField(default=0)
    
    # Algorithm metrics
    boost_score = models.PositiveIntegerField(default=0, help_text="Calculated boost score for ranking")
    priority_level = models.PositiveSmallIntegerField(default=0, help_text="Priority level in search results")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property', 'status']),
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['boost_score', 'priority_level']),
        ]
    
    def __str__(self):
        return f"Boost - {self.property.title} ({self.get_status_display()})"
    
    def is_active_boost(self):
        return self.status == self.Status.ACTIVE and self.start_date <= timezone.now() <= self.end_date
    
    def calculate_boost_score(self):
        """Calculate boost score based on package and time remaining"""
        if not self.is_active_boost():
            self.boost_score = 0
            return
        
        base_score = self.package.boost_multiplier * 100
        
        # Time remaining factor (more time = slightly higher score)
        time_remaining = (self.end_date - timezone.now()).total_seconds() / 86400  # days
        time_factor = min(time_remaining / 30, 1) * 20  # Max 20 points
        
        # Package features
        feature_score = 0
        if self.package.featured_placement:
            feature_score += 30
        if self.package.top_of_search:
            feature_score += 25
        if self.package.badge_highlight:
            feature_score += 15
        if self.package.priority_support:
            feature_score += 10
        
        self.boost_score = int(base_score + time_factor + feature_score)
        self.priority_level = min(self.boost_score // 50, 10)  # Priority 0-10
        self.save(update_fields=['boost_score', 'priority_level'])


class BoostAnalytics(models.Model):
    """Analytics for boosted properties"""
    boost = models.ForeignKey(PropertyBoost, on_delete=models.CASCADE, related_name='analytics')
    
    date = models.DateField()
    views = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    inquiries = models.PositiveIntegerField(default=0)
    favorites = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    
    # Conversion metrics
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Comparison with non-boosted period
    avg_daily_views_before = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    view_increase_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['boost', 'date']
        indexes = [
            models.Index(fields=['boost', 'date']),
        ]
    
    def __str__(self):
        return f"Analytics - {self.boost.property.title} ({self.date})"
