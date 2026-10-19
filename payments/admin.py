from django.contrib import admin

from .models import PaymentAttempt, PaymentEvent


class PaymentEventInline(admin.TabularInline):
    model = PaymentEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_key", "source", "reported_status", "status_before", "status_after", "note", "received_at")


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("reference", "client", "owner", "provider", "amount", "status", "relation_granted", "created_at")
    list_filter = ("provider", "status", "relation_granted")
    search_fields = ("reference", "provider_transaction_id", "client__username", "owner__username")
    # Les statuts sont pilotés par le fournisseur : lecture seule dans l'admin.
    readonly_fields = [f.name for f in PaymentAttempt._meta.fields]
    inlines = [PaymentEventInline]

    def has_add_permission(self, request):
        return False
