from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q

from .models import Favorite
from properties.models import Property
from accounts.models import User


@login_required
def favorite_list(request):
    """List all favorites for the current user"""
    favorites = Favorite.objects.filter(user=request.user).select_related('property', 'property__owner').prefetch_related('property__images')
    return render(request, "favorites/list.html", {"favorites": favorites})


@login_required
@require_POST
def toggle_favorite(request):
    """Toggle favorite status for a property"""
    property_id = request.POST.get('property_id')
    if not property_id:
        return JsonResponse({'success': False, 'error': 'Property ID required'}, status=400)
    
    property_obj = get_object_or_404(
        Property,
        pk=property_id,
        is_published=True,
        is_validated=True,
        owner__isnull=False,
        owner__role=User.Role.OWNER,
        owner__is_active=True,
    )
    
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        property=property_obj
    )
    
    if not created:
        # Already exists, remove it
        favorite.delete()
        is_favorited = False
        message = "Retiré des favoris"
    else:
        is_favorited = True
        message = "Ajouté aux favoris"
    
    return JsonResponse({
        'success': True,
        'is_favorited': is_favorited,
        'message': message
    })


@login_required
def remove_favorite(request, property_id):
    """Remove a specific favorite"""
    favorite = get_object_or_404(Favorite, user=request.user, property_id=property_id)
    favorite.delete()
    messages.success(request, "Bien retiré de vos favoris.")
    return redirect("favorites:list")
