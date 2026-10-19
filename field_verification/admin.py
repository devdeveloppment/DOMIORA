from django.contrib import admin

from .models import AdminDecision, MissionEvidence, MissionLog, VerificationMission


class EvidenceInline(admin.TabularInline):
    model = MissionEvidence
    extra = 0
    readonly_fields = ("uploaded_by", "image", "caption", "device_captured_at", "latitude", "longitude",
                       "accuracy_m", "location_source", "uploaded_at")


class LogInline(admin.TabularInline):
    model = MissionLog
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "action", "from_status", "to_status", "note", "created_at")


class DecisionInline(admin.TabularInline):
    model = AdminDecision
    extra = 0
    can_delete = False
    readonly_fields = ("admin", "decision", "reason", "created_at")


@admin.register(VerificationMission)
class VerificationMissionAdmin(admin.ModelAdmin):
    list_display = ("pk", "owner", "property", "verifier", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("owner__username", "owner__last_name", "verifier__username")
    # Les transitions passent par le tableau de bord (journalisées) : statut en lecture seule ici.
    readonly_fields = ("status", "submitted_at", "closed_at", "started_at")
    inlines = [EvidenceInline, DecisionInline, LogInline]
