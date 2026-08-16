from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend

from accounts.models import User, IdentityVerificationRequest
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

from services.n8n_service import send_identity_verification
from services.email_service import send_identity_verification_email
from services.ai_assistant import get_assistant_response


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_published=True).prefetch_related("images", "amenities").select_related("owner")
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAgentOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "property_type", "transaction_type", "status", "country", "city", "bedrooms",
        "bathrooms", "is_featured", "is_validated", "owner__verification_status",
    ]
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
        serializer.save(
            user=self.request.user,
            agent=getattr(property.owner, "agent_profile", None),
        )


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


@api_view(['POST'])
def verification_submit(request):
    """
    Submit identity verification documents
    POST /api/verification/submit/
    """
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return Response(
            {'error': 'Authentification requise'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Check if user is an owner
    if request.user.role != User.Role.OWNER:
        return Response(
            {'error': 'Seuls les propriétaires peuvent soumettre une vérification d\'identité'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Check if there's already a pending verification
    pending_verification = IdentityVerificationRequest.objects.filter(
        owner=request.user,
        status__in=[IdentityVerificationRequest.Status.PENDING, 
                   IdentityVerificationRequest.Status.RESUBMISSION_REQUESTED]
    ).first()
    
    if pending_verification:
        return Response(
            {'error': 'Vous avez déjà une demande de vérification en cours'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get documents from request
    id_card_front = request.FILES.get('id_card_front')
    id_card_back = request.FILES.get('id_card_back')
    id_document_type = request.data.get('id_document_type', '')
    id_document_number = request.data.get('id_document_number', '')
    
    if not id_card_front or not id_card_back:
        return Response(
            {'error': 'Les deux faces de la pièce d\'identité sont requises'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate file types and sizes
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    max_size = 5 * 1024 * 1024  # 5MB
    
    for file in [id_card_front, id_card_back]:
        if file.content_type not in allowed_types:
            return Response(
                {'error': f'Type de fichier non autorisé: {file.content_type}. Utilisez JPG, PNG ou WebP.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if file.size > max_size:
            return Response(
                {'error': f'Fichier trop volumineux. Maximum 5MB autorisé.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Create verification request
    verification = IdentityVerificationRequest.objects.create(
        owner=request.user,
        id_document_front=id_card_front,
        id_document_back=id_card_back,
        id_document_type=id_document_type,
        id_document_number=id_document_number,
        status=IdentityVerificationRequest.Status.PENDING
    )
    
    # Update owner status
    request.user.verification_status = User.VerificationStatus.PENDING
    request.user.save(update_fields=['verification_status'])
    
    # Send to n8n
    n8n_response = send_identity_verification(verification)
    
    return Response({
        'message': 'Documents envoyés pour vérification',
        'status': 'pending',
        'verification_id': verification.id,
        'n8n_sent': n8n_response.get('success', False)
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verification_resume(request, verification_id):
    """
    Resume verification workflow from n8n
    POST /api/verification/resume/{verification_id}/
    """
    try:
        verification = IdentityVerificationRequest.objects.get(id=verification_id)
    except IdentityVerificationRequest.DoesNotExist:
        return Response(
            {'error': 'Demande de vérification non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    decision = request.data.get('decision')
    reason = request.data.get('reason', '')
    reviewed_by_email = request.data.get('reviewed_by', '')
    
    if decision not in ['validated', 'rejected']:
        return Response(
            {'error': 'Décision invalide. Utilisez "validated" ou "rejected"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find admin user by email
    admin_user = None
    if reviewed_by_email:
        try:
            admin_user = User.objects.get(email=reviewed_by_email, role=User.Role.ADMIN)
        except User.DoesNotExist:
            pass
    
    if not admin_user:
        # Use first admin as fallback
        admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    
    if decision == 'validated':
        verification.approve(admin_user)
        # Create notification
        Notification.objects.create(
            user=verification.owner,
            title='Identité validée',
            message='Votre identité a été validée. Vous pouvez maintenant publier vos propriétés.',
            notification_type='verification_approved',
            link='/dashboard/proprietaire/verification-identite/'
        )
        # Send email
        send_identity_verification_email(verification.owner, 'approved')
    else:
        verification.reject(admin_user, reason)
        # Create notification
        Notification.objects.create(
            user=verification.owner,
            title='Identité refusée',
            message=f'Votre identité a été refusée. Raison: {reason}. Veuillez envoyer de nouveaux documents.',
            notification_type='verification_rejected',
            link='/dashboard/proprietaire/verification-identite/'
        )
        # Send email
        send_identity_verification_email(verification.owner, 'rejected', reason)
    
    return Response({
        'message': f'Vérification {decision} avec succès',
        'status': verification.status
    })


@api_view(['POST'])
def chat_assistant(request):
    """
    AI Chat Assistant for DOMIORA
    POST /api/chat/
    """
    message = request.data.get('message', '').strip()
    history = request.data.get('history', [])
    
    if not message:
        return Response(
            {'error': 'Message is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Detect user role if authenticated
    user_role = None
    if request.user.is_authenticated:
        if request.user.role == User.Role.OWNER:
            user_role = 'owner'
        elif request.user.role == User.Role.ADMIN:
            user_role = 'admin'
    else:
        user_role = 'visitor'
    
    try:
        # Get AI response with intent detection and role context
        result = get_assistant_response(message, conversation_history=history, user_role=user_role)
        
        return Response({
            'response': result.get('response'),
            'properties': result.get('properties', [])
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def admin_notification_webhook(request):
    """
    Webhook endpoint for n8n to send admin notifications
    POST /api/admin/notifications/
    """
    notification_type = request.data.get('notification_type')
    title = request.data.get('title', '')
    message = request.data.get('message', '')
    user_id = request.data.get('user_id')
    
    if not all([notification_type, title, message, user_id]):
        return Response(
            {'error': 'Missing required fields: notification_type, title, message, user_id'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id)
        
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type
        )
        
        return Response({'status': 'success'}, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
