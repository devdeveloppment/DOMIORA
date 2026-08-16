from django.db import models
from django.conf import settings


class FurnitureModel(models.Model):
    """3D furniture models for AR visualization"""
    class Category(models.TextChoices):
        LIVING_ROOM = "living_room", "Salon"
        BEDROOM = "bedroom", "Chambre"
        KITCHEN = "kitchen", "Cuisine"
        BATHROOM = "bathroom", "Salle de bain"
        OFFICE = "office", "Bureau"
        DINING = "dining", "Salle à manger"
        OUTDOOR = "outdoor", "Extérieur"
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    
    # 3D model files
    model_file = models.FileField(upload_to='ar_furniture/models/', help_text="GLB/GLTF 3D model file")
    thumbnail = models.ImageField(upload_to='ar_furniture/thumbnails/')
    
    # Dimensions (in meters)
    width = models.DecimalField(max_digits=5, decimal_places=2, help_text="Largeur en mètres")
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Hauteur en mètres")
    depth = models.DecimalField(max_digits=5, decimal_places=2, help_text="Profondeur en mètres")
    
    # Pricing info
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Prix de référence")
    currency = models.CharField(max_length=5, default="USD")
    
    # Metadata
    brand = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=50, blank=True)
    material = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class ARConfiguration(models.Model):
    """AR configuration for property visualization"""
    property = models.OneToOneField('properties.Property', on_delete=models.CASCADE, related_name='ar_config')
    
    # Room dimensions (optional, for better AR placement)
    room_width = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Largeur de la pièce en mètres")
    room_length = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Longueur de la pièce en mètres")
    room_height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Hauteur de la pièce en mètres")
    
    # Recommended furniture
    recommended_furniture = models.ManyToManyField(FurnitureModel, blank=True, related_name='recommended_for')
    
    # AR settings
    enable_ar = models.BooleanField(default=True, help_text="Activer la visualisation AR pour cette propriété")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Configuration AR - {self.property.title}"
