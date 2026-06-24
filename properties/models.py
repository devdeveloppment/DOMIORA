from django.db import models
from django.urls import reverse
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

    agent = models.ForeignKey("agents.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="properties")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    property_type = models.CharField(max_length=30, choices=PropertyType.choices, default=PropertyType.APPARTEMENT)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, default=TransactionType.VENTE)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    country = models.CharField(max_length=80, default="US")
    city = models.CharField(max_length=120)
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
    is_published = models.BooleanField(default=True)
    is_validated = models.BooleanField(default=True, help_text="Annonce validée par un administrateur")
    views_count = models.PositiveIntegerField(default=0)
    virtual_tour_url = models.URLField(blank=True, help_text="Lien d'une visite virtuelle (Matterport, vidéo 360°, YouTube...)")
    stock_image_urls = models.JSONField(default=list, blank=True, help_text="Images de démonstration (URLs) utilisées tant qu'aucune photo n'est uploadée")
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
        return self.stock_image_urls or []

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


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="properties/%Y/%m/")
    is_primary = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image #{self.pk} - {self.property.title}"
