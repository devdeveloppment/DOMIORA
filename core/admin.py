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


from .models import Donation, DonationEvent  # noqa: E402


class DonationEventInline(admin.TabularInline):
    model = DonationEvent
    extra = 0
    can_delete = False
    readonly_fields = ("source", "reported_status", "status_before", "status_after", "event_key", "received_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    """Consultation seule : un don ne change d'état que par vérification auprès du prestataire."""
    list_display = ("reference", "amount", "currency", "provider", "status", "is_test", "created_at", "confirmed_at")
    list_filter = ("status", "is_test", "provider")
    inlines = [DonationEventInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
