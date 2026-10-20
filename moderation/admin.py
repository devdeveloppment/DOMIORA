from django.contrib import admin

from .models import ListingReport, ReportEvent


class ReportEventInline(admin.TabularInline):
    model = ReportEvent
    extra = 0
    can_delete = False
    readonly_fields = ("action", "actor", "from_status", "to_status", "note", "is_public", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ListingReport)
class ListingReportAdmin(admin.ModelAdmin):
    list_display = ("pk", "category", "property", "reported_owner", "reason", "status", "created_at")
    list_filter = ("status", "category", "reason")
    # Stockage privé sans URL publique : la pièce jointe se consulte depuis le tableau de bord (vue protégée).
    exclude = ("attachment",)
    inlines = [ReportEventInline]


@admin.register(ReportEvent)
class ReportEventAdmin(admin.ModelAdmin):
    """Historique d'audit : consultation seule."""
    list_display = ("report", "action", "actor", "to_status", "is_public", "created_at")
    list_filter = ("action", "is_public")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
