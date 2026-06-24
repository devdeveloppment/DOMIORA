from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("user", "agent", "property", "scheduled_at", "status")
    list_filter = ("status",)
    list_editable = ("status",)
