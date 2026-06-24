from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator

from .decorators import role_required
from favorites.models import Favorite
from rental_requests.models import PropertyRequest
from accounts.models import User


@role_required(User.Role.BUYER)
def buyer_overview(request):
    favorites_count = Favorite.objects.filter(user=request.user).count()
    requests = PropertyRequest.objects.filter(user=request.user).select_related("property")
    context = {
        "dash_role": "buyer", "active": "overview",
        "favorites_count": favorites_count,
        "requests_count": requests.count(),
        "pending_count": requests.filter(status="en_attente").count(),
        "accepted_count": requests.filter(status="acceptee").count(),
        "recent_requests": requests[:5],
        "recent_favorites": Favorite.objects.filter(user=request.user).select_related("property")[:4],
    }
    return render(request, "dashboard/buyer/overview.html", context)


@role_required(User.Role.BUYER)
def buyer_favorites(request):
    favorites = Favorite.objects.filter(user=request.user).select_related("property").prefetch_related("property__images")
    paginator = Paginator(favorites, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/buyer/favorites.html", {"page_obj": page_obj, "dash_role": "buyer", "active": "favorites"})


@role_required(User.Role.BUYER)
def buyer_requests(request):
    requests_qs = PropertyRequest.objects.filter(user=request.user).select_related("property", "agent__user")
    paginator = Paginator(requests_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/buyer/requests.html", {"page_obj": page_obj, "dash_role": "buyer", "active": "requests"})
