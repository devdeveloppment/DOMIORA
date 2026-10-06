from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('owner', 'reviewer', 'rating', 'is_verified', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_verified', 'is_approved', 'created_at')
    search_fields = ('owner__username', 'reviewer__username', 'title', 'comment')
    list_editable = ('is_approved',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Informations de base', {
            'fields': ('owner', 'reviewer', 'property', 'rating', 'title', 'comment')
        }),
        ('Ratings détaillés', {
            'fields': ('communication_rating', 'professionalism_rating', 'responsiveness_rating'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('is_verified', 'is_approved')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )