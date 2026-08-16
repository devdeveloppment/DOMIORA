from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class RecentSale(models.Model):
    """Recent property sales for price comparison"""
    property_type = models.CharField(max_length=30)
    transaction_type = models.CharField(max_length=10)
    
    # Location
    city = models.CharField(max_length=120)
    neighborhood = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
    
    # Property details
    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.PositiveSmallIntegerField(default=0)
    surface_area = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Sale details
    sale_price = models.DecimalField(max_digits=14, decimal_places=2)
    sale_date = models.DateField()
    
    # Additional info
    condition = models.CharField(max_length=50, blank=True, help_text="État du bien")
    year_built = models.PositiveSmallIntegerField(null=True, blank=True)
    
    # Source
    source = models.CharField(max_length=100, blank=True, help_text="Source de la donnée")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['city', 'neighborhood', 'sale_date']),
            models.Index(fields=['property_type', 'transaction_type']),
            models.Index(fields=['surface_area']),
        ]
    
    def __str__(self):
        return f"{self.city} - {self.sale_price:,.0f} ({self.sale_date})"


class PriceEstimation(models.Model):
    """Price estimation for properties based on recent sales"""
    property = models.OneToOneField('properties.Property', on_delete=models.CASCADE, related_name='price_estimation')
    
    # Estimated values
    estimated_min_price = models.DecimalField(max_digits=14, decimal_places=2)
    estimated_max_price = models.DecimalField(max_digits=14, decimal_places=2)
    estimated_avg_price = models.DecimalField(max_digits=14, decimal_places=2)
    
    # Comparison with listing price
    listing_price = models.DecimalField(max_digits=14, decimal_places=2)
    price_difference_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_priced_fairly = models.BooleanField(default=True)
    
    # Analysis details
    comparable_sales_count = models.PositiveIntegerField(default=0)
    comparable_sales_ids = models.JSONField(default=list, blank=True)
    
    # Market position
    market_position = models.CharField(max_length=20, choices=[
        ('below_market', 'En dessous du marché'),
        ('at_market', 'Dans la moyenne'),
        ('above_market', 'Au-dessus du marché'),
    ], default='at_market')
    
    # Confidence score (0-100)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    
    # Metadata
    analysis_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-analysis_date']
        indexes = [
            models.Index(fields=['property', 'analysis_date']),
            models.Index(fields=['market_position']),
        ]
    
    def __str__(self):
        return f"Estimation - {self.property.title}: {self.estimated_avg_price:,.0f}"
    
    def calculate_price_difference(self):
        if self.listing_price and self.estimated_avg_price:
            difference = ((self.listing_price - self.estimated_avg_price) / self.estimated_avg_price) * 100
            self.price_difference_percent = round(difference, 2)
            self.is_priced_fairly = abs(difference) <= 15  # Within 15% is considered fair
            if difference < -15:
                self.market_position = 'below_market'
            elif difference > 15:
                self.market_position = 'above_market'
            else:
                self.market_position = 'at_market'


class GeographicPriceAnalysis(models.Model):
    """Geographic-based price analysis for neighborhoods"""
    city = models.CharField(max_length=120)
    neighborhood = models.CharField(max_length=120, blank=True)
    
    # Price statistics
    avg_price_per_sqm = models.DecimalField(max_digits=12, decimal_places=2, help_text="Average price per m²")
    min_price_per_sqm = models.DecimalField(max_digits=12, decimal_places=2)
    max_price_per_sqm = models.DecimalField(max_digits=12, decimal_places=2)
    median_price_per_sqm = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Market trends
    price_trend = models.CharField(max_length=20, choices=[
        ('rising', 'En hausse'),
        ('stable', 'Stable'),
        ('falling', 'En baisse'),
    ], default='stable')
    price_change_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Market activity
    total_listings = models.PositiveIntegerField(default=0)
    total_sales = models.PositiveIntegerField(default=0)
    avg_days_on_market = models.PositiveIntegerField(default=0)
    
    # Analysis period
    analysis_period_start = models.DateField()
    analysis_period_end = models.DateField()
    
    # Confidence metrics
    data_points_count = models.PositiveIntegerField(default=0)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['city', 'neighborhood']
        indexes = [
            models.Index(fields=['city', 'neighborhood']),
            models.Index(fields=['price_trend']),
        ]
    
    def __str__(self):
        location = f"{self.city}" + (f", {self.neighborhood}" if self.neighborhood else "")
        return f"Analyse prix - {location}: {self.avg_price_per_sqm:,.0f}/m²"
    
    def get_price_range(self, surface_area):
        """Calculate estimated price range for a given surface area"""
        min_price = self.min_price_per_sqm * surface_area
        max_price = self.max_price_per_sqm * surface_area
        avg_price = self.avg_price_per_sqm * surface_area
        return {
            'min': min_price,
            'max': max_price,
            'avg': avg_price,
        }
