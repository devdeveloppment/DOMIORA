from django.contrib import admin
from .models import Testimonial, ContactMessage


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "rating", "is_published", "created_at")
    list_filter = ("is_published", "rating")
    list_editable = ("is_published",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    list_filter = ("is_read",)
    list_editable = ("is_read",)
