from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from agents.models import Agent, Specialty
from properties.models import Property, PropertyImage, Amenity
from favorites.models import Favorite
from rental_requests.models import PropertyRequest
from transactions.models import Transaction
from notifications.models import Notification

from .serializers import (
    UserSerializer, AgentSerializer, SpecialtySerializer, PropertySerializer,
    PropertyImageSerializer, AmenitySerializer, FavoriteSerializer,
    PropertyRequestSerializer, TransactionSerializer, NotificationSerializer,
)
from .permissions import IsOwnerOrReadOnly, IsAgentOwnerOrReadOnly


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_published=True).prefetch_related("images", "amenities").select_related("agent__user")
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAgentOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["property_type", "transaction_type", "status", "country", "city", "bedrooms", "is_featured"]
    search_fields = ["title", "city", "address", "description"]
    ordering_fields = ["price", "created_at", "views_count", "surface_area"]
    lookup_field = "slug"


class AmenityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Agent.objects.select_related("user").prefetch_related("specialties")
    serializer_class = AgentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__first_name", "user__last_name", "agency_name"]
    ordering_fields = ["rating", "years_experience"]


class SpecialtyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related("property")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PropertyRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PropertyRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == "admin":
            return PropertyRequest.objects.all()
        if user.role == "agent":
            return PropertyRequest.objects.filter(agent__user=user)
        return PropertyRequest.objects.filter(user=user)

    def perform_create(self, serializer):
        property = serializer.validated_data["property"]
        serializer.save(user=self.request.user, agent=property.agent)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == "admin":
            return Transaction.objects.all()
        if user.role == "agent":
            return Transaction.objects.filter(agent__user=user)
        return Transaction.objects.filter(client=user)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_read"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response({"status": "ok"})


class MeView(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        return Response(UserSerializer(request.user).data)
