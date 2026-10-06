from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg
from accounts.models import User
from properties.models import Property
from .models import Review
from .forms import ReviewForm


@login_required
def create_review(request, owner_id):
    """Create a review for an owner"""
    owner = get_object_or_404(User, pk=owner_id, role=User.Role.OWNER)
    
    # Check if user already reviewed this owner
    if Review.objects.filter(owner=owner, reviewer=request.user).exists():
        messages.warning(request, "Vous avez déjà noté ce propriétaire.")
        return redirect("properties:detail", slug=owner.properties.first().slug) if owner.properties.exists() else "properties:list"
    
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.owner = owner
            review.reviewer = request.user
            review.save()
            messages.success(request, "Votre avis a été soumis pour validation.")
            return redirect("properties:detail", slug=owner.properties.first().slug) if owner.properties.exists() else "properties:list"
    else:
        form = ReviewForm()
    
    context = {
        "owner": owner,
        "form": form,
    }
    return render(request, "ratings/create_review.html", context)


@login_required
def owner_reviews(request, owner_id):
    """View all reviews for an owner"""
    owner = get_object_or_404(User, pk=owner_id, role=User.Role.OWNER)
    reviews = owner.reviews.filter(is_approved=True).select_related('reviewer', 'property_obj').order_by('-created_at')
    
    context = {
        "owner": owner,
        "reviews": reviews,
        "average_rating": owner.average_rating,
        "reviews_count": owner.reviews_count,
    }
    return render(request, "ratings/owner_reviews.html", context)