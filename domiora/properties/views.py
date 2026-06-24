from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from .models import Property, Amenity
from favorites.models import Favorite
from rental_requests.models import PropertyRequest
from rental_requests.forms import PropertyRequestForm


def property_list(request):
    qs = Property.objects.filter(is_published=True, is_validated=True)

    transaction = request.GET.get("transaction")
    if transaction in ("vente", "location"):
        qs = qs.filter(transaction_type=transaction)

    property_type = request.GET.get("type")
    if property_type:
        qs = qs.filter(property_type=property_type)

    country = request.GET.get("country")
    if country:
        qs = qs.filter(country=country)

    city = request.GET.get("city")
    if city:
        qs = qs.filter(city__icontains=city)

    price_min = request.GET.get("price_min")
    if price_min:
        qs = qs.filter(price__gte=price_min)
    price_max = request.GET.get("price_max")
    if price_max:
        qs = qs.filter(price__lte=price_max)

    bedrooms = request.GET.get("bedrooms")
    if bedrooms:
        qs = qs.filter(bedrooms__gte=bedrooms)

    bathrooms = request.GET.get("bathrooms")
    if bathrooms:
        qs = qs.filter(bathrooms__gte=bathrooms)

    surface_min = request.GET.get("surface_min")
    if surface_min:
        qs = qs.filter(surface_area__gte=surface_min)

    status = request.GET.get("status")
    if status == "vendu_loue":
        qs = qs.filter(status__in=["vendu", "loue"])
    elif status == "disponible":
        qs = qs.filter(status="disponible")

    q = request.GET.get("q")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(city__icontains=q) | Q(address__icontains=q))

    sort = request.GET.get("sort", "recent")
    sort_map = {
        "recent": "-created_at",
        "price_asc": "price",
        "price_desc": "-price",
        "popular": "-views_count",
    }
    qs = qs.order_by(sort_map.get(sort, "-created_at"))

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(Favorite.objects.filter(user=request.user).values_list("property_id", flat=True))

    view_mode = request.GET.get("view", "grid")

    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
        "property_types": Property.PropertyType.choices,
        "countries": Property.objects.values_list("country", flat=True).distinct(),
        "favorite_ids": favorite_ids,
        "view_mode": view_mode,
        "current_sort": sort,
        "request_get": request.GET,
    }
    return render(request, "properties/list.html", context)


def property_detail(request, slug):
    property = get_object_or_404(
        Property.objects.select_related("agent", "agent__user").prefetch_related("images", "amenities"),
        slug=slug,
    )
    Property.objects.filter(pk=property.pk).update(views_count=property.views_count + 1)

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, property=property).exists()

    similar = Property.objects.filter(
        is_published=True, city=property.city
    ).exclude(pk=property.pk)[:3]

    request_form = PropertyRequestForm()

    if request.method == "POST" and request.user.is_authenticated:
        request_form = PropertyRequestForm(request.POST)
        if request_form.is_valid():
            property_request = request_form.save(commit=False)
            property_request.user = request.user
            property_request.property = property
            property_request.agent = property.agent
            property_request.save()
            messages.success(request, "Votre demande a bien été envoyée à l'agent.")
            return redirect("properties:detail", slug=property.slug)

    context = {
        "property": property,
        "is_favorite": is_favorite,
        "similar": similar,
        "request_form": request_form,
    }
    return render(request, "properties/detail.html", context)


@login_required
def toggle_favorite(request, pk):
    property = get_object_or_404(Property, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, property=property)
    if not created:
        favorite.delete()
        messages.info(request, "Bien retiré de vos favoris.")
    else:
        messages.success(request, "Bien ajouté à vos favoris.")
    next_url = request.POST.get("next") or request.GET.get("next") or property.get_absolute_url()
    return redirect(next_url)


def compare_properties(request):
    ids = [i for i in request.GET.get("ids", "").split(",") if i.isdigit()][:3]
    properties = list(Property.objects.filter(pk__in=ids).prefetch_related("amenities", "agent__user"))
    properties.sort(key=lambda p: ids.index(str(p.pk)))
    for p in properties:
        p.amenity_names = set(p.amenities.values_list("name", flat=True))
    all_amenities = sorted({name for p in properties for name in p.amenity_names})
    return render(request, "properties/compare.html", {"properties": properties, "all_amenities": all_amenities})
