from django.contrib import admin

from .models import ListingReport


@admin.register(ListingReport)
class ListingReportAdmin(admin.ModelAdmin):
    list_display = ("pk", "property", "reason", "status", "created_at")
    list_filter = ("status", "reason")
