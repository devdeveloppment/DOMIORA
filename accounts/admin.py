from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_suspended", "is_staff", "date_joined")
    list_filter = ("role", "is_suspended", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (
        ("DOMIORA", {"fields": ("role", "phone", "avatar", "bio", "is_suspended")}),
    )
