from django.contrib import admin
from .models import PropertyRequest


@admin.register(PropertyRequest)
class PropertyRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "property", "request_type", "status", "agent", "created_at")
    list_filter = ("request_type", "status")
    search_fields = ("user__username", "property__title")
    list_editable = ("status",)
