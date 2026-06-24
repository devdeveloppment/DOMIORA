from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import redirect
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse("admin:site_settings_sitesettings_change", args=[obj.pk]))
