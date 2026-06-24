from django.contrib import admin
from .models import SubscriptionPlan, AgentSubscription, PaymentHistory

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'max_listings', 'is_active', 'order')
    list_filter = ('is_active', 'is_recommended')

@admin.register(AgentSubscription)
class AgentSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('agent', 'plan', 'status', 'start_date', 'end_date', 'auto_renew')
    list_filter = ('status', 'plan', 'auto_renew')
    search_fields = ('agent__user__first_name', 'agent__user__last_name', 'agent__user__email')

@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'amount', 'currency', 'status', 'payment_method', 'payment_date')
    list_filter = ('status', 'payment_method')
    search_fields = ('subscription__agent__user__first_name', 'subscription__agent__user__last_name', 'transaction_id')


