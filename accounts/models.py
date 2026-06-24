from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class User(AbstractUser):
    """Custom user model supporting three roles: buyer/tenant, agent, admin."""

    class Role(models.TextChoices):
        BUYER = "buyer", "Acheteur / Locataire"
        AGENT = "agent", "Agent immobilier"
        ADMIN = "admin", "Administrateur"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.BUYER)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    is_suspended = models.BooleanField(default=False, help_text="Compte désactivé par un administrateur")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_buyer(self):
        return self.role == self.Role.BUYER

    @property
    def is_agent_role(self):
        return self.role == self.Role.AGENT

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def get_absolute_url(self):
        return reverse("accounts:profile")

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return "https://ui-avatars.com/api/?background=7c3aed&color=fff&name=" + (self.get_full_name() or self.username).replace(" ", "+")
