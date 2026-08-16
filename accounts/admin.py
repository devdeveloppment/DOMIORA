from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, IdentityVerificationRequest


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_suspended", "is_staff", "date_joined")
    list_filter = ("role", "is_suspended", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (
        ("DOMIORA", {"fields": ("role", "phone", "avatar", "bio", "is_suspended")}),
    )


@admin.register(IdentityVerificationRequest)
class IdentityVerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "status", "submitted_at", "reviewed_at", "reviewed_by")
    list_filter = ("status", "submitted_at", "reviewed_at")
    search_fields = ("owner__username", "owner__email", "id_document_number")
    readonly_fields = ("submitted_at", "reviewed_at")
    date_hierarchy = "submitted_at"
