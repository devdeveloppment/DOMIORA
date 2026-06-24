from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("property", "transaction_type", "amount", "commission_amount", "status", "agent", "client", "transaction_date")
    list_filter = ("transaction_type", "status")
    search_fields = ("property__title", "client__username")
    date_hierarchy = "transaction_date"
