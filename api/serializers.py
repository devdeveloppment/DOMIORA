from rest_framework import serializers
from accounts.models import User
from agents.models import Agent, Specialty
from properties.models import Property, PropertyImage, Amenity
from favorites.models import Favorite
from rental_requests.models import PropertyRequest
from transactions.models import Transaction
from notifications.models import Notification


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "phone", "role", "avatar", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name"]


class AgentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    specialties = SpecialtySerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            "id", "user", "full_name", "agency_name", "license_number", "bio",
            "commission_rate", "years_experience", "rating", "is_verified",
            "specialties", "facebook", "instagram", "linkedin", "twitter", "youtube",
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name()


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ["id", "name", "icon"]


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ["id", "image", "is_primary", "order"]


class PropertySerializer(serializers.ModelSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    agent = AgentSerializer(read_only=True)
    primary_image = serializers.ReadOnlyField()
    badge_label = serializers.ReadOnlyField()

    class Meta:
        model = Property
        fields = [
            "id", "title", "slug", "description", "property_type", "transaction_type",
            "price", "currency", "country", "city", "address", "latitude", "longitude",
            "bedrooms", "bathrooms", "surface_area", "floors", "year_built", "status",
            "is_featured", "is_published", "views_count", "agent", "images", "amenities",
            "primary_image", "badge_label", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "views_count", "created_at", "updated_at"]


class FavoriteSerializer(serializers.ModelSerializer):
    property_detail = PropertySerializer(source="property", read_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "user", "property", "property_detail", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class PropertyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyRequest
        fields = [
            "id", "user", "property", "agent", "request_type", "message",
            "move_in_date", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "agent", "status", "created_at", "updated_at"]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id", "property", "agent", "client", "transaction_type", "amount",
            "commission_amount", "status", "transaction_date", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "notification_type", "link", "is_read", "created_at"]
        read_only_fields = ["id", "created_at"]
