from django.contrib import admin

from .models import OwnerSubscription, Plan, SubscriptionEvent, SubscriptionPayment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price_xof", "visibility_level", "max_promoted_listings", "is_proposal", "is_active")


class EventInline(admin.TabularInline):
    model = SubscriptionEvent
    extra = 0
    can_delete = False
    readonly_fields = ("action", "from_status", "to_status", "note", "created_at")


@admin.register(OwnerSubscription)
class OwnerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("owner", "plan", "status", "current_period_end", "cancel_at_period_end")
    list_filter = ("status", "plan")
    readonly_fields = ("status",)  # transitions uniquement via les services (journalisées)
    inlines = [EventInline]


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "owner", "plan", "amount", "status", "environment", "created_at")
    list_filter = ("status", "environment")
    readonly_fields = [f.name for f in SubscriptionPayment._meta.fields]

    def has_add_permission(self, request):
        return False
