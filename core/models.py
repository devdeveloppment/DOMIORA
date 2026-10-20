import uuid

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Testimonial(models.Model):
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True, help_text="Ex: Acheteuse | Paris")
    content = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    avatar = models.ImageField(upload_to="testimonials/", blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.subject or 'Sans sujet'}"


class BlogPost(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    excerpt = models.TextField(max_length=300, help_text="Courte description pour l'accueil")
    content = models.TextField()
    featured_image = models.ImageField(upload_to="blog/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False, help_text="Mettre en avant sur l'accueil")
    meta_description = models.CharField(max_length=160, blank=True, help_text="SEO meta description")
    meta_keywords = models.CharField(max_length=255, blank=True, help_text="SEO keywords séparés par des virgules")
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['is_featured']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('core:blog_detail', kwargs={'slug': self.slug})


class Donation(models.Model):
    """
    Don volontaire à DOMIORA (montant libre). Confirmé uniquement par vérification serveur
    auprès du prestataire ; un don de test (simulation ou FedaPay sandbox) n'est jamais compté
    comme encaissé (is_test).
    """

    class Provider(models.TextChoices):
        SIMULATION = "simulation", "Simulation (démonstration)"
        FEDAPAY = "fedapay", "FedaPay"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Reçu"
        DECLINED = "declined", "Refusé"
        CANCELED = "canceled", "Annulé"
        FAILED = "failed", "Échec technique"

    TERMINAL = {Status.APPROVED, Status.DECLINED, Status.CANCELED, Status.FAILED}

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    donor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="donations")
    donor_email = models.EmailField(blank=True)
    donor_phone = models.CharField(max_length=30, blank=True)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XOF")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_test = models.BooleanField(default=True, db_index=True)
    simulated_outcome = models.CharField(max_length=20, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Don"

    def __str__(self):
        return f"Don {self.amount} {self.currency} ({self.get_status_display()})"

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL


class DonationEvent(models.Model):
    """Journal idempotent : une même notification (clé) n'est appliquée qu'une fois."""

    donation = models.ForeignKey(Donation, on_delete=models.CASCADE, related_name="events")
    event_key = models.CharField(max_length=150, unique=True)
    source = models.CharField(max_length=20)
    reported_status = models.CharField(max_length=30, blank=True)
    status_before = models.CharField(max_length=20, blank=True)
    status_after = models.CharField(max_length=20, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at"]
