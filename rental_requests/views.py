from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import PropertyRequest
from properties.models import Property
from notifications.models import Notification
import json


@require_http_methods(["POST"])
def create_property_request(request):
    """
    Créer une demande de visite, d'achat ou de location
    Permet aux utilisateurs connectés et aux guests (non connectés) de créer des demandes
    """
    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        
        property_id = data.get("property_id")
        request_type = data.get("request_type", "visite")
        message = data.get("message", "")
        move_in_date = data.get("move_in_date", None)
        
        # Vérifier que l'utilisateur a bien débloqué la propriété (payé)
        property_obj = get_object_or_404(Property, id=property_id)
        
        # Pour les utilisateurs non connectés (guest), créer un compte automatiquement
        if not request.user.is_authenticated:
            guest_name = data.get("guest_name", "")
            guest_email = data.get("guest_email", "")
            guest_phone = data.get("guest_phone", "")
            
            if not guest_name or not guest_email or not guest_phone:
                return JsonResponse({
                    "success": False,
                    "message": "Veuillez fournir votre nom, email et téléphone pour continuer."
                }, status=400)
            
            # Créer un compte client automatiquement
            from accounts.models import User
            import random
            import string
            
            # Générer un username unique
            username = f"guest_{guest_name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
            while User.objects.filter(username=username).exists():
                username = f"guest_{guest_name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
            
            # Générer un mot de passe aléatoire
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            guest_user = User.objects.create_user(
                username=username,
                email=guest_email,
                password=password,
                first_name=guest_name.split()[0] if ' ' in guest_name else guest_name,
                last_name=guest_name.split()[-1] if ' ' in guest_name else '',
                phone=guest_phone,
                role=User.Role.CLIENT
            )
            
            # Auto-unlock the property for this new guest user
            from properties.models import PropertyUnlock
            PropertyUnlock.objects.get_or_create(user=guest_user, property=property_obj)
            
            # Auto-login the guest user
            from django.contrib.auth import login
            login(request, guest_user)
            
            # Force session role to 'client'
            request.session['dash_role'] = 'client'
            request.session.modified = True
            
            user = guest_user
        else:
            user = request.user
        
        # Créer la demande
        property_request = PropertyRequest.objects.create(
            user=user,
            property=property_obj,
            request_type=request_type,
            message=message,
            move_in_date=move_in_date,
            status="en_attente"
        )
        
        # Créer une notification pour le propriétaire
        Notification.objects.create(
            user=property_obj.owner,
            notification_type="demande",
            title=f"Nouvelle demande de {property_request.get_request_type_display()}",
            message=f"{user.get_full_name() or user.email} souhaite {property_request.get_request_type_display().lower()} votre bien : {property_obj.title}",
            related_id=property_request.id,
            related_model="PropertyRequest"
        )
        
        # Envoyer un email au propriétaire
        try:
            subject = f"Nouvelle demande de {property_request.get_request_type_display()} pour {property_obj.title}"
            
            html_message = render_to_string(
                "rental_requests/email_owner_notification.html",
                {
                    "owner": property_obj.owner,
                    "user": user,
                    "property": property_obj,
                    "request_type": property_request.get_request_type_display(),
                    "message": message,
                    "request_id": property_request.id,
                    "site_url": f"{request.scheme}://{request.get_host()}",
                }
            )
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [property_obj.owner.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Erreur envoi email: {e}")
        
        # Réponse JSON si AJAX
        if request.content_type == "application/json":
            return JsonResponse({
                "success": True,
                "message": "Demande de visite envoyée avec succès!",
                "request_id": property_request.id
            })
        
        # Sinon redirection avec message
        from django.contrib import messages
        messages.success(request, "Votre demande de visite a été envoyée au propriétaire!")
        return redirect("properties:detail", slug=property_obj.slug)
        
    except Exception as e:
        if request.content_type == "application/json":
            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=400)
        
        from django.contrib import messages
        messages.error(request, "Erreur lors de l'envoi de la demande")
        return redirect("properties:detail", slug=property_obj.slug)
