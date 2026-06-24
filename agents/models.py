from django.db import models
from django.urls import reverse
from django.conf import settings


class Specialty(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name_plural = "Specialties"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Agent(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_profile")
    agency_name = models.CharField(max_length=150, blank=True)
    license_number = models.CharField(max_length=60, blank=True, verbose_name="N° de licence")
    bio = models.TextField(blank=True)
    commission_rate = models.DecimalField(max_digits=4, decimal_places=1, default=5.0, help_text="En %")
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    is_verified = models.BooleanField(default=False)
    specialties = models.ManyToManyField(Specialty, blank=True, related_name="agents")
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    response_time_hours = models.PositiveIntegerField(default=24)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def get_absolute_url(self):
        return reverse("agents:detail", kwargs={"pk": self.pk})

    @property
    def active_properties_count(self):
        return self.properties.filter(is_published=True).exclude(status="vendu").exclude(status="loue").count()

    @property
    def sold_or_rented_count(self):
        return self.properties.filter(status__in=["vendu", "loue"]).count()

    @property
    def total_properties_count(self):
        return self.properties.count()

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(avg=models.Avg("rating"))["avg"]
        return round(agg, 1) if agg else self.rating

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def is_top_agent(self):
        return self.average_rating >= 4.7 and self.sold_or_rented_count >= 3


class AgentReview(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_reviews")
    rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("agent", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.agent} ({self.rating}★)"
