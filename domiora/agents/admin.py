from django.contrib import admin
from .models import Agent, Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "agency_name", "is_verified", "rating", "commission_rate", "total_properties_count")
    list_filter = ("is_verified", "specialties")
    search_fields = ("user__username", "user__first_name", "user__last_name", "agency_name")
    autocomplete_fields = ("user",)
    filter_horizontal = ("specialties",)


from .models import AgentReview


@admin.register(AgentReview)
class AgentReviewAdmin(admin.ModelAdmin):
    list_display = ("agent", "user", "rating", "created_at")
    list_filter = ("rating",)
