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

    # Règle : avis réservé aux clients ayant une relation payée, confirmée et achevée.
    from .eligibility import review_eligibility

    payment, refusal = review_eligibility(request.user, owner)
    if refusal:
        messages.error(request, refusal)
        return redirect("properties:list")

    # Check if user already reviewed this owner
    if Review.objects.filter(owner=owner, reviewer=request.user).exists():
        messages.warning(request, "Vous avez déjà noté ce propriétaire.")
        return redirect("ratings:owner_reviews", owner_id=owner.pk)
    
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.owner = owner
            review.reviewer = request.user
            review.payment = payment
            review.is_verified = True
            review.save()
            messages.success(request, "Votre avis a été soumis pour validation.")
            return redirect("ratings:owner_reviews", owner_id=owner.pk)
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