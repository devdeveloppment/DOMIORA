from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from dashboard.decorators import role_required
from properties.models import Property

from .models import ListingReport
from .services import ReportError, process_report, reportable_targets, submit_report


@login_required
def report_listing(request, slug):
    """Signalement depuis la page d'une annonce (formulaire court)."""
    prop = get_object_or_404(Property, slug=slug, is_published=True, is_validated=True)
    if prop.owner_id == request.user.pk:
        messages.info(request, "Vous ne pouvez pas signaler votre propre annonce.")
        return redirect(prop.get_absolute_url())
    if request.method == "POST":
        try:
            submit_report(request.user, reason=request.POST.get("reason", ""), property_obj=prop,
                          details=request.POST.get("details", ""), attachment=request.FILES.get("attachment"))
        except ReportError as error:
            messages.error(request, str(error))
            if "déjà en cours" in str(error) or "aujourd'hui" in str(error):
                return redirect(prop.get_absolute_url())
        else:
            messages.success(request, "Merci. Votre signalement a été transmis à l'équipe DOMIORA. "
                                      "Vous pouvez suivre son traitement dans « Mes signalements ».")
            return redirect(prop.get_absolute_url())
    return render(request, "moderation/report_form.html", {"property": prop, "reasons": ListingReport.Reason.choices})


# --- Espace client -----------------------------------------------------------

@role_required(User.Role.CLIENT)
def client_reports(request):
    reports = ListingReport.objects.filter(reporter=request.user).select_related("property", "reported_owner")
    return render(request, "moderation/client_list.html", {
        "reports": reports, "dash_role": "client", "active": "reports",
    })


@role_required(User.Role.CLIENT)
def client_report_new(request):
    properties, owners = reportable_targets(request.user)
    form = {"category": request.GET.get("type", ListingReport.Category.LISTING), "property": "", "owner": "",
            "reason": "", "details": ""}
    preselected = request.GET.get("bien")
    if preselected:
        match = next((p for p in properties if p.slug == preselected), None)
        if match:
            form["property"] = str(match.pk)
    if request.method == "POST":
        form = {k: request.POST.get(k, "") for k in ("category", "property", "owner", "reason", "details")}
        # Seules les cibles proposées au client sont acceptées (pas d'identifiant arbitraire).
        prop = next((p for p in properties if str(p.pk) == form["property"]), None)
        owner = next((o for o in owners if str(o.pk) == form["owner"]), None)
        if form["property"] and prop is None or form["owner"] and owner is None:
            messages.error(request, "Sélection invalide.")
        else:
            try:
                report = submit_report(request.user, category=form["category"], reason=form["reason"],
                                       property_obj=prop, reported_owner=owner, details=form["details"],
                                       attachment=request.FILES.get("attachment"))
            except ReportError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, "Signalement transmis. L'équipe DOMIORA l'examinera avant toute décision.")
                return redirect("dashboard:client_report_detail", pk=report.pk)
    return render(request, "moderation/client_form.html", {
        "form": form, "properties": properties, "owners": owners,
        "categories": ListingReport.Category.choices, "reasons": ListingReport.Reason.choices,
        "dash_role": "client", "active": "reports",
    })


@role_required(User.Role.CLIENT)
def client_report_detail(request, pk):
    # 404 (et non 403) pour un signalement d'un autre compte : son existence n'est pas révélée.
    report = get_object_or_404(ListingReport.objects.select_related("property", "reported_owner"), pk=pk, reporter=request.user)
    return render(request, "moderation/client_detail.html", {
        "report": report, "events": report.events.filter(is_public=True),
        "dash_role": "client", "active": "reports",
    })


def report_attachment(request, pk):
    """Pièce jointe privée : visible par l'administration et par l'auteur du signalement uniquement."""
    from core.views_private import _is_admin, private_file_response

    report = get_object_or_404(ListingReport, pk=pk)
    if not (_is_admin(request.user) or (request.user.is_authenticated and report.reporter_id == request.user.pk)):
        raise Http404
    return private_file_response(report.attachment)


# --- Administration ------------------------------------------------------------

@role_required(User.Role.ADMIN)
def admin_reports(request):
    reports = ListingReport.objects.select_related("property", "reporter", "reported_owner")
    status = request.GET.get("status", "active")
    if status == "active":
        reports = reports.filter(status__in=ListingReport.ACTIVE_STATUSES)
    elif status != "all":
        reports = reports.filter(status=status)
    category = request.GET.get("type", "")
    if category in ListingReport.Category.values:
        reports = reports.filter(category=category)
    counts = ListingReport.objects.aggregate(
        open=Count("id", filter=Q(status=ListingReport.Status.OPEN)),
        reviewing=Count("id", filter=Q(status=ListingReport.Status.REVIEWING)),
        closed=Count("id", filter=~Q(status__in=ListingReport.ACTIVE_STATUSES)),
    )
    return render(request, "moderation/admin_list.html", {
        "page_obj": Paginator(reports, 20).get_page(request.GET.get("page")), "status_filter": status,
        "type_filter": category, "statuses": ListingReport.Status.choices, "categories": ListingReport.Category.choices,
        "counts": counts, "dash_role": "admin", "active": "listing_reports",
    })


@role_required(User.Role.ADMIN)
def admin_report_detail(request, pk):
    report = get_object_or_404(
        ListingReport.objects.select_related("property", "property__owner", "reported_owner", "reporter", "handled_by"), pk=pk)
    if request.method == "POST":
        try:
            process_report(report, request.user, status=request.POST.get("action") or None,
                           internal_note=request.POST.get("admin_note", ""),
                           public_message=request.POST.get("public_message", ""),
                           unpublish=request.POST.get("unpublish") == "on")
        except ReportError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Signalement mis à jour.")
        return redirect("dashboard:admin_listing_report", pk=pk)
    related = ListingReport.objects.exclude(pk=report.pk)
    target_q = Q()
    if report.property_id:
        target_q |= Q(property_id=report.property_id)
    if report.reported_owner_id:
        target_q |= Q(reported_owner_id=report.reported_owner_id)
    others = related.filter(target_q).select_related("property")[:20] if target_q else []
    return render(request, "moderation/admin_detail.html", {
        "report": report, "others": others, "events": report.events.select_related("actor"),
        "dash_role": "admin", "active": "listing_reports",
    })
