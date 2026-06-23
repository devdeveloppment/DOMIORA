from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Agent, AgentReview
from .forms import AgentReviewForm
from properties.models import Property


def agent_list(request):
    agents = Agent.objects.select_related("user").prefetch_related("specialties").order_by("-rating")
    q = request.GET.get("q")
    if q:
        agents = agents.filter(user__first_name__icontains=q) | agents.filter(user__last_name__icontains=q)
    specialty = request.GET.get("specialty")
    if specialty:
        agents = agents.filter(specialties__name=specialty)
    paginator = Paginator(agents, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    from .models import Specialty
    return render(request, "agents/list.html", {"page_obj": page_obj, "specialties": Specialty.objects.all()})


def agent_detail(request, pk):
    agent = get_object_or_404(Agent.objects.select_related("user").prefetch_related("specialties"), pk=pk)
    properties = Property.objects.filter(agent=agent, is_published=True)
    sold_count = properties.filter(status__in=["vendu", "loue"]).count()
    reviews = agent.reviews.select_related("user")[:10]

    review_form = AgentReviewForm()
    user_has_reviewed = False
    if request.user.is_authenticated:
        user_has_reviewed = AgentReview.objects.filter(agent=agent, user=request.user).exists()
        if request.method == "POST" and not user_has_reviewed:
            review_form = AgentReviewForm(request.POST)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.agent = agent
                review.user = request.user
                review.save()
                messages.success(request, "Merci pour votre avis !")
                return redirect("agents:detail", pk=agent.pk)

    context = {
        "agent": agent,
        "properties": properties[:9],
        "active_count": properties.exclude(status__in=["vendu", "loue"]).count(),
        "sold_count": sold_count,
        "reviews": reviews,
        "review_form": review_form,
        "user_has_reviewed": user_has_reviewed,
    }
    return render(request, "agents/detail.html", context)
