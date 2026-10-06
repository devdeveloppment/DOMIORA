from django.db import models
from django.core.cache import cache
from django.conf import settings as django_settings


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default="DOMIORA")
    tagline = models.CharField(max_length=255, default="Votre rêve, notre priorité")
    logo = models.ImageField(upload_to="settings/", blank=True, null=True)
    favicon = models.ImageField(upload_to="settings/", blank=True, null=True)
    contact_email = models.EmailField(default="denistchil@gmail.com")
    contact_phone = models.CharField(max_length=50, default="+228 90 56 78 48 / +228 73 06 01 18")
    address = models.CharField(max_length=255, default="Lomé, Togo")
    opening_hours_weekdays = models.CharField(max_length=80, default="Lun - Ven: 9h - 18h")
    opening_hours_weekend = models.CharField(max_length=80, default="Sam: 10h - 16h")
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    whatsapp = models.CharField(max_length=50, blank=True, help_text="Numéro WhatsApp avec l'indicatif (ex: +33600000000)")
    smtp_host = models.CharField(max_length=120, blank=True, help_text="Configuré réellement via le fichier .env")
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=120, blank=True)
    smtp_use_tls = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Paramètres du site"
        verbose_name_plural = "Paramètres du site"

    def __str__(self):
        return self.site_name

    def _clean_file_url(self, field):
        """Retourne l'URL correcte d'un ImageField en évitant le double préfixe /media/media/."""
        if not field:
            return None
        # Stockage distant (Cloudinary en production) : URL fournie par le stockage.
        try:
            url = field.url
        except Exception:
            url = ""
        if url.startswith("http"):
            return url
        name = field.name or ""
        # Si le nom commence par 'media/', on le supprime car MEDIA_URL est déjà /media/
        if name.startswith("media/"):
            name = name[len("media/"):]
        media_url = django_settings.MEDIA_URL.rstrip("/")
        return f"{media_url}/{name}"

    @property
    def logo_url(self):
        return self._clean_file_url(self.logo)

    @property
    def favicon_url(self):
        return self._clean_file_url(self.favicon)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete("site_settings_singleton")

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj = cache.get("site_settings_singleton")
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set("site_settings_singleton", obj, 300)  # Cache 5 minutes
        return obj

