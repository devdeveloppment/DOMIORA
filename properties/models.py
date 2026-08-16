from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings


class Amenity(models.Model):
    name = models.CharField(max_length=80, unique=True)
    icon = models.CharField(max_length=40, blank=True, help_text="Nom d'icône Heroicons (ex: wifi, fire, sparkles)")

    class Meta:
        verbose_name_plural = "Amenities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Property(models.Model):
    class PropertyType(models.TextChoices):
        APPARTEMENT = "appartement", "Appartement"
        VILLA = "villa", "Villa"
        STUDIO = "studio", "Studio"
        PENTHOUSE = "penthouse", "Penthouse"
        MAISON_DE_VILLE = "maison_de_ville", "Maison de ville"
        COMMERCIAL = "commercial", "Commercial"
        TERRAIN = "terrain", "Terrain"
        FERME = "ferme", "Ferme"
        COTTAGE = "cottage", "Cottage"
        LOFT = "loft", "Loft"
        DUPLEX = "duplex", "Duplex"
        TRIPLEX = "triplex", "Triplex"
        RANCH = "ranch", "Ranch"
        MOBILE_HOME = "mobile_home", "Mobile Home"
        COPROPRIETE = "copropriete", "Copropriété"
        BUNGALOW = "bungalow", "Bungalow"
        CHATEAU = "chateau", "Château"

    class TransactionType(models.TextChoices):
        VENTE = "vente", "À vendre"
        LOCATION = "location", "À louer"

    class Status(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        VENDU = "vendu", "Vendu"
        LOUE = "loue", "Loué"
        BROUILLON = "brouillon", "Brouillon"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="properties")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    property_type = models.CharField(max_length=30, choices=PropertyType.choices, default=PropertyType.APPARTEMENT)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, default=TransactionType.VENTE)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    country = models.CharField(max_length=80, default="US")
    city = models.CharField(max_length=120)
    neighborhood = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(default=0, verbose_name="Chambres")
    bathrooms = models.PositiveSmallIntegerField(default=0, verbose_name="Salles de bain")
    surface_area = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="m²")
    floors = models.PositiveSmallIntegerField(default=1)
    year_built = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DISPONIBLE)
    is_featured = models.BooleanField(default=False)
    is_exclusive = models.BooleanField(default=False, help_text="Mandat exclusif DOMIORA")
    is_published = models.BooleanField(default=False)
    
    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Validée"
        REJECTED = "rejected", "Refusée"
        
    validation_status = models.CharField(max_length=20, choices=ValidationStatus.choices, default=ValidationStatus.PENDING)
    is_validated = models.BooleanField(default=False, help_text="Annonce validée par un administrateur")
    views_count = models.PositiveIntegerField(default=0)
    class VideoStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        PROCESSING = "processing", "En cours de création"
        DONE = "done", "Terminé"
        FAILED = "failed", "Échoué"
        
    virtual_tour_video = models.FileField(upload_to="properties/generated_tours/", null=True, blank=True, help_text="Vidéo générée automatiquement à partir des images")
    video_status = models.CharField(max_length=20, choices=VideoStatus.choices, default=VideoStatus.PENDING)

    virtual_tour_url = models.URLField(blank=True, help_text="Lien d'une visite virtuelle (Matterport, vidéo 360°, YouTube...)")
    uploaded_tour_video = models.FileField(upload_to="properties/uploaded_tours/", blank=True, null=True, verbose_name="Vidéo de visite filmée", help_text="Vidéo MP4 filmée par le propriétaire montrant la propriété")
    stock_image_urls = models.JSONField(default=list, blank=True, help_text="Images de démonstration (URLs) utilisées tant qu'aucune photo n'est uploadée")
    nearby_services = models.JSONField(default=list, blank=True, help_text="Services de quartier avec distances estimées")
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="properties")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Properties"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "is_validated", "status"]),
            models.Index(fields=["transaction_type", "property_type"]),
            models.Index(fields=["city"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:200]
            slug = base_slug
            i = 1
            while Property.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base_slug}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)
        self._notify_matching_search_alerts()

    def _matches_search_alert(self, alert):
        if not alert.is_active:
            return False
        if alert.city and self.city.lower() != alert.city.lower():
            return False
        if alert.property_type and self.property_type != alert.property_type:
            return False
        if alert.transaction_type and self.transaction_type != alert.transaction_type:
            return False
        if alert.price_min is not None and self.price < alert.price_min:
            return False
        if alert.price_max is not None and self.price > alert.price_max:
            return False
        if alert.bedrooms_min is not None and self.bedrooms < alert.bedrooms_min:
            return False
        return True

    def _notify_matching_search_alerts(self):
        if not (self.is_published and self.is_validated):
            return
        if not self.city:
            return

        from notifications.models import Notification

        alerts = SearchAlert.objects.filter(is_active=True, user__is_active=True)
        for alert in alerts:
            if not self._matches_search_alert(alert):
                continue
            if alert.last_notified and alert.last_notified >= self.created_at:
                continue

            Notification.objects.create(
                user=alert.user,
                title="Nouvelle propriété correspond à votre alerte",
                message=f"{self.title} vient d’être publiée à {self.city} et correspond à votre alerte “{alert.name}”.",
                notification_type="info",
                link=self.get_absolute_url(),
            )
            alert.last_notified = timezone.now()
            alert.save(update_fields=["last_notified"])

    def get_absolute_url(self):
        return reverse("properties:detail", kwargs={"slug": self.slug})

    @property
    def primary_image(self):
        gallery = self.gallery()
        return gallery[0] if gallery else "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800"

    def gallery(self):
        """Returns the list of image URLs to display: real uploads first, else demo stock photos."""
        uploaded = [img.image.url for img in self.images.all()]
        if uploaded:
            return uploaded
        return self.stock_image_urls or ["https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1200&q=80"]

    @property
    def is_new(self):
        from django.utils import timezone
        from datetime import timedelta
        return self.created_at >= timezone.now() - timedelta(days=10)

    @property
    def badge_label(self):
        if self.status == self.Status.VENDU:
            return "VENDU"
        if self.status == self.Status.LOUE:
            return "LOUÉ"
        if self.transaction_type == self.TransactionType.LOCATION:
            return "À LOUER"
        return "À VENDRE"

    @property
    def price_display(self):
        suffix = "/mois" if self.transaction_type == self.TransactionType.LOCATION else ""
        return f"{self.price:,.0f} FCFA{suffix}".replace(",", " ")

    @property
    def owner_verified(self):
        return bool(self.owner and self.owner.is_verified_owner)

    @property
    def owner_verification_label(self):
        if not self.owner:
            return ""
        if self.owner.is_verified_owner:
            return "✅ Propriétaire vérifié"
        if self.owner.verification_status == self.owner.VerificationStatus.PENDING:
            return "⚪ Vérification en cours"
        return ""

    @property
    def verification_badge_html(self):
        """Return HTML for verification badge"""
        if self.is_validated:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700">✔️ Annonce vérifiée</span>'
        elif self.validation_status == self.ValidationStatus.PENDING:
            return '<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-amber-100 text-amber-700">⏳ En attente</span>'
        return ''

    @property
    def favorites_count(self):
        """Count of favorites for this property"""
        return self.favorited_by.count()

    @property
    def status_badges(self):
        """Return list of automatic status badges"""
        badges = []
        if self.is_new:
            badges.append(('🟢 Nouvelle annonce', 'bg-green-100 text-green-700'))
        if self.views_count > 100:
            badges.append(('🔥 Très consultée', 'bg-orange-100 text-orange-700'))
        if self.favorites_count > 10:
            badges.append(('⭐ Populaire', 'bg-purple-100 text-purple-700'))
        return badges

    @property
    def quality_score(self):
        """Calculate property quality score (0-100)"""
        score = 0
        # Owner verification (20 points)
        if self.owner and self.owner.is_verified_owner:
            score += 20
        # Property validation (20 points)
        if self.is_validated:
            score += 20
        # Images (25 points)
        if self.images.count() >= 5:
            score += 25
        elif self.images.count() >= 3:
            score += 15
        elif self.images.count() >= 1:
            score += 5
        # Description (20 points)
        if len(self.description) > 200:
            score += 20
        elif len(self.description) > 100:
            score += 10
        # Location (15 points)
        if self.latitude and self.longitude:
            score += 15
        elif self.city:
            score += 5
        if self.neighborhood:
            score += 5
        return min(score, 100)


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="properties/%Y/%m/")
    is_primary = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image #{self.pk} - {self.property.title}"

class PropertyUnlock(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="unlocked_properties")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="unlocks")
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "property")

    def __str__(self):
        return f"{self.user} unlocked {self.property.title}"


class PropertyView(models.Model):
    """Track when a user views a property"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="viewed_properties")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="property_views")
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_key = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["user", "-viewed_at"]),
            models.Index(fields=["property", "-viewed_at"]),
            models.Index(fields=["-viewed_at"]),
        ]

    def __str__(self):
        return f"{self.user or 'Anonymous'} viewed {self.property.title}"


class PropertyComparison(models.Model):
    """Track properties selected for comparison by a user"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="property_comparisons")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="comparisons")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "property")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} comparing {self.property.title}"


class SearchAlert(models.Model):
    """User's saved search alerts"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="search_alerts")
    name = models.CharField(max_length=100, help_text="Name for this alert (e.g., 'Villa à Lomé')")
    city = models.CharField(max_length=120, blank=True)
    property_type = models.CharField(max_length=30, blank=True)
    transaction_type = models.CharField(max_length=10, blank=True)
    price_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bedrooms_min = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_notified = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.name}"
