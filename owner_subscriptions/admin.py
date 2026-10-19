from django.contrib import admin

from .models import OwnerSubscription, Plan, SubscriptionEvent


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price_xof", "period_days", "is_demo", "is_active")


class EventInline(admin.TabularInline):
    model = SubscriptionEvent
    extra = 0
    can_delete = False
    readonly_fields = ("action", "from_status", "to_status", "note", "created_at")


@admin.register(OwnerSubscription)
class OwnerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("owner", "plan", "status", "is_simulated", "current_period_end")
    list_filter = ("status", "is_simulated")
    inlines = [EventInline]
