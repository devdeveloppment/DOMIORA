# Modèles pour la gestion des propriétés immobilières dans DOMIORA
# Ce fichier définit la structure complète pour les annonces, images, documents et fonctionnalités associées

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings

from properties.video.storage import video_storage


class Amenity(models.Model):
    """
    Modèle représentant les équipements et services disponibles sur une propriété.
    Exemples : WiFi, piscine, parking, climatisation, etc.
    """
    name = models.CharField(max_length=80, unique=True)  # Nom unique de l'équipement.
    icon = models.CharField(max_length=40, blank=True, help_text="Nom d'icône Heroicons (ex: wifi, fire, sparkles)")  # Icône utilisée dans les templates.

    class Meta:
        verbose_name_plural = "Amenities"  # Nom pluriel pour l'interface d'administration.
        ordering = ["name"]  # Tri alphabétique.

    def __str__(self):
        return self.name


class Property(models.Model):
    """
    Modèle principal représentant une propriété immobilière.
    Il contient les informations de base, les caractéristiques, la localisation,
    les données de publication et de validation de l'annonce.
    """
    class PropertyType(models.TextChoices):
        """Types de propriétés disponibles"""
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
        """Types de transactions possibles"""
        VENTE = "vente", "À vendre"
        LOCATION = "location", "À louer"

    class Status(models.TextChoices):
        """Statuts de disponibilité de la propriété"""
        DISPONIBLE = "disponible", "Disponible"
        VENDU = "vendu", "Vendu"
        LOUE = "loue", "Loué"
        BROUILLON = "brouillon", "Brouillon"

    # Relation avec le propriétaire
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="properties")  # Propriétaire du bien
    
    # Informations de base
    title = models.CharField(max_length=200)  # Titre de l'annonce
    slug = models.SlugField(max_length=220, unique=True, blank=True)  # URL slug unique
    description = models.TextField(blank=True)  # Description détaillée
    
    # Type et transaction
    property_type = models.CharField(max_length=30, choices=PropertyType.choices, default=PropertyType.APPARTEMENT)  # Type de bien
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, default=TransactionType.VENTE)  # Type de transaction
    
    # Prix et devise
    price = models.DecimalField(max_digits=14, decimal_places=2)  # Prix du bien
    currency = models.CharField(max_length=5, default="USD")  # Devise
    
    # Localisation
    country = models.CharField(max_length=80, default="US")  # Pays
    city = models.CharField(max_length=120)  # Ville
    neighborhood = models.CharField(max_length=120, blank=True)  # Quartier
    address = models.CharField(max_length=255, blank=True)  # Adresse complète
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)  # Coordonnée GPS latitude
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)  # Coordonnée GPS longitude
    
    # Caractéristiques
    bedrooms = models.PositiveSmallIntegerField(default=0, verbose_name="Chambres")  # Nombre de chambres
    bathrooms = models.PositiveSmallIntegerField(default=0, verbose_name="Salles de bain")  # Nombre de salles de bain
    surface_area = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="m²")  # Surface en m²
    floors = models.PositiveSmallIntegerField(default=1)  # Nombre d'étages
    year_built = models.PositiveSmallIntegerField(null=True, blank=True)  # Année de construction
    
    # Statuts et flags
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DISPONIBLE)  # Statut de disponibilité
    is_featured = models.BooleanField(default=False)  # Bien en vedette
    is_exclusive = models.BooleanField(default=False, help_text="Mandat exclusif DOMIORA")  # Mandat exclusif
    is_published = models.BooleanField(default=False)  # Annonce publiée
    
    # Validation admin
    class ValidationStatus(models.TextChoices):
        """Statuts de validation par l'administrateur"""
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Validée"
        REJECTED = "rejected", "Refusée"
        
    validation_status = models.CharField(max_length=20, choices=ValidationStatus.choices, default=ValidationStatus.PENDING)  # Statut de validation
    is_validated = models.BooleanField(default=False, help_text="Annonce validée par un administrateur")  # Validation admin
    views_count = models.PositiveIntegerField(default=0)  # Compteur de vues
    
    # Visite virtuelle et vidéo
    class VideoStatus(models.TextChoices):
        """Statuts de génération de la visite virtuelle (cf. properties/video/)."""
        PENDING = "pending", "En attente"
        PREPARING = "preparing", "Préparation"
        GENERATING = "generating", "Génération en cours"
        ASSEMBLING = "assembling", "Assemblage"
        DONE = "done", "Terminé"
        FAILED = "failed", "Erreur"

    # Stockage vidéo : Cloudinary (resource_type "video") si CLOUDINARY_URL est défini, sinon disque local.
    virtual_tour_video = models.FileField(upload_to="properties/generated_tours/", storage=video_storage, null=True, blank=True, help_text="Vidéo générée automatiquement à partir des images")  # Vidéo générée automatiquement
    video_status = models.CharField(max_length=20, choices=VideoStatus.choices, default=VideoStatus.PENDING)  # Statut de génération vidéo
    video_progress = models.PositiveSmallIntegerField(default=0, help_text="Progression de la génération (0-100)")
    video_error = models.CharField(max_length=255, blank=True, help_text="Message affiché au propriétaire en cas d'échec")
    video_job_id = models.CharField(max_length=36, blank=True, help_text="Génération en cours : une tâche plus ancienne ne peut pas écraser le résultat")

    virtual_tour_url = models.URLField(blank=True, help_text="Lien d'une visite virtuelle (Matterport, vidéo 360°, YouTube...)")  # Lien visite virtuelle externe
    uploaded_tour_video = models.FileField(upload_to="properties/uploaded_tours/", storage=video_storage, blank=True, null=True, verbose_name="Vidéo de visite filmée", help_text="Vidéo MP4 filmée par le propriétaire montrant la propriété")  # Vidéo uploadée
    
    # Données JSON flexibles
    stock_image_urls = models.JSONField(default=list, blank=True, help_text="Images de démonstration (URLs) utilisées tant qu'aucune photo n'est uploadée")  # Images de démonstration
    nearby_services = models.JSONField(default=list, blank=True, help_text="Services de quartier avec distances estimées")  # Services de proximité
    
    # Relations
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="properties")  # Équipements disponibles
    
    # Horodatage
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création
    updated_at = models.DateTimeField(auto_now=True)  # Date de dernière modification

    class Meta:
        verbose_name_plural = "Properties"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "is_validated", "status"]),
            models.Index(fields=["transaction_type", "property_type"]),
            models.Index(fields=["city"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["validation_status"]),
            models.Index(fields=["price"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Génère un slug unique et vérifie s'il faut notifier les alertes de recherche."""
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
        """Vérifie si une propriété correspond à une alerte sauvegardée par un utilisateur."""
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
        """Envoie une notification aux utilisateurs dont l'alerte correspond à cette propriété."""
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
        """Retourne l'image principale de la propriété, ou une image par défaut si aucune n'existe."""
        gallery = self.gallery()
        return gallery[0] if gallery else "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800"

    def gallery(self):
        """Retourne la liste des URLs d'images à afficher : uploads réels en priorité, sinon images de démonstration."""
        uploaded = [img.image.url for img in self.images.all()]
        if uploaded:
            return uploaded
        return self.stock_image_urls or ["https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1200&q=80"]

    @property
    def is_new(self):
        """Indique si la propriété est récente (ajoutée dans les 10 derniers jours)."""
        from django.utils import timezone
        from datetime import timedelta
        return self.created_at >= timezone.now() - timedelta(days=10)

    @property
    def is_promo(self):
        """Indique si la propriété est mise en avant comme annonce promo."""
        return self.is_featured

    @property
    def badge_label(self):
        """Retourne le libellé affiché pour la badge de statut de bien."""
        if self.status == self.Status.VENDU:
            return "VENDU"
        if self.status == self.Status.LOUE:
            return "LOUÉ"
        if self.transaction_type == self.TransactionType.LOCATION:
            return "À LOUER"
        return "À VENDRE"

    @property
    def price_display(self):
        """Formate le prix pour l'affichage utilisateur dans l'interface."""
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
        if self.owner.verification_status in [self.owner.VerificationStatus.PENDING_DOCUMENTS, 
                                            self.owner.VerificationStatus.PENDING_FIELD_VISIT,
                                            self.owner.VerificationStatus.FIELD_VISIT_COMPLETED]:
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
        if hasattr(self, '_fav_count'):
            return self._fav_count
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
        """Calcule un score de qualité du bien sur 100, basé sur sa complétude et sa vérification."""
        score = 0
        # Vérification du propriétaire : 20 points.
        if self.owner and self.owner.is_verified_owner:
            score += 20
        # Validation administrative : 20 points.
        if self.is_validated:
            score += 20
        # Photos : 25 points.
        if self.images.count() >= 5:
            score += 25
        elif self.images.count() >= 3:
            score += 15
        elif self.images.count() >= 1:
            score += 5
        # Description : 20 points.
        if len(self.description) > 200:
            score += 20
        elif len(self.description) > 100:
            score += 10
        # Localisation : 15 points.
        if self.latitude and self.longitude:
            score += 15
        elif self.city:
            score += 5
        if self.neighborhood:
            score += 5
        return min(score, 100)


class PropertyImage(models.Model):
    """Image associée à une propriété dans la galerie publique."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="properties/%Y/%m/")
    is_primary = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image #{self.pk} - {self.property.title}"
    
    def save(self, *args, **kwargs):
        """Convertit les images téléchargées au format WebP pour optimiser le stockage et le rendu."""
        if self.image:
            from PIL import Image
            import io
            from django.core.files.base import ContentFile
            
            # Read the image
            img = Image.open(self.image)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as WebP with good quality
            webp_io = io.BytesIO()
            img.save(webp_io, format='WebP', quality=85, method=6)
            webp_io.seek(0)
            
            # Change extension to .webp
            import os
            base_name = os.path.basename(self.image.name)
            webp_name = base_name.rsplit('.', 1)[0] + '.webp'
            
            # Replace the image with WebP version
            self.image.save(webp_name, ContentFile(webp_io.read()), save=False)
        
        super().save(*args, **kwargs)


class PropertyDocument(models.Model):
    """Document joint lié à une propriété (titre, plan, diagnostic, certificat, etc.)."""
    
    class DocumentType(models.TextChoices):
        TITRE_PROPRIETE = "titre_propriete", "Titre de propriété"
        PLAN = "plan", "Plan/Schéma"
        CERTIFICAT_CONSTRUCTION = "certificat_construction", "Certificat de construction"
        FACTURE_SERVICES = "facture_services", "Factures services (eau, électricité)"
        DIAGNOSTIQUE = "diagnostique", "Diagnostique/Inspection"
        CONTRAT_LOCATION = "contrat_location", "Contrat de location"
        AUTRE = "autre", "Autre document"
    
    related_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="properties/documents/%Y/%m/", help_text="PDF, JPG, PNG, DOC autorisés")
    document_type = models.CharField(max_length=30, choices=DocumentType.choices, default=DocumentType.AUTRE)
    title = models.CharField(max_length=200, help_text="Titre du document")
    description = models.TextField(blank=True, help_text="Description optionnelle")
    order = models.PositiveSmallIntegerField(default=0, help_text="Ordre d'affichage")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ["order", "-uploaded_at"]
        verbose_name_plural = "Property Documents"
    
    def __str__(self):
        return f"{self.title} - {self.related_property.title}"
    
    @property
    def file_extension(self):
        """Retourne l'extension du document, en majuscules."""
        return self.file.name.split('.')[-1].upper()

    @property
    def file_size_mb(self):
        """Retourne la taille du fichier en mégaoctets."""
        return round(self.file.size / (1024 * 1024), 2)


class PropertyUnlock(models.Model):
    """Enregistrement d'un accès débloqué pour un client sur une propriété donnée."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="unlocked_properties")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="unlocks")
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "property")

    def __str__(self):
        return f"{self.user} unlocked {self.property.title}"


class PropertyView(models.Model):
    """Enregistre une consultation d'une propriété par un utilisateur."""
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
    """Trace les biens sélectionnés pour une comparaison côté utilisateur."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="property_comparisons")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="comparisons")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "property")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} comparing {self.property.title}"


class SearchAlert(models.Model):
    """Alerte de recherche sauvegardée par un utilisateur."""
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
