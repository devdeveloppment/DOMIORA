from django.contrib import admin
from .models import Property, PropertyImage, Amenity


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "icon")
    search_fields = ("name",)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "transaction_type", "property_type", "price", "city", "status", "is_published", "is_featured", "agent")
    list_filter = ("transaction_type", "property_type", "status", "is_published", "is_featured", "country")
    search_fields = ("title", "city", "address", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PropertyImageInline]
    filter_horizontal = ("amenities",)
    list_editable = ("is_published", "is_featured", "status")
    autocomplete_fields = ("agent",)
