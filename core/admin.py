from django.contrib import admin
from .models import Testimonial, ContactMessage, BlogPost


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


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'is_featured', 'view_count', 'published_at', 'created_at')
    list_filter = ('status', 'is_featured', 'published_at', 'created_at')
    search_fields = ('title', 'excerpt', 'content')
    list_editable = ('status', 'is_featured')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('view_count', 'created_at', 'updated_at')
    fieldsets = (
        ('Informations de base', {
            'fields': ('title', 'slug', 'author', 'status', 'is_featured')
        }),
        ('Contenu', {
            'fields': ('excerpt', 'content', 'featured_image')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': ('view_count', 'created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
