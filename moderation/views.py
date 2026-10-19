from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from dashboard.decorators import role_required
from notifications.models import Notification
from properties.models import Property

from .models import ListingReport

MAX_REPORTS_PER_DAY = 5


@login_required
def report_listing(request, slug):
    prop = get_object_or_404(Property, slug=slug, is_published=True, is_validated=True)
    if prop.owner_id == request.user.pk:
        messages.info(request, "Vous ne pouvez pas signaler votre propre annonce.")
        return redirect(prop.get_absolute_url())
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        if reason not in ListingReport.Reason.values:
            messages.error(request, "Choisissez un motif.")
        elif ListingReport.objects.filter(property=prop, reporter=request.user,
                                          status__in=[ListingReport.Status.OPEN, ListingReport.Status.REVIEWING]).exists():
            messages.info(request, "Votre signalement pour cette annonce est déjà en cours d'examen.")
            return redirect(prop.get_absolute_url())
        elif ListingReport.objects.filter(reporter=request.user,
                                          created_at__gte=timezone.now() - timedelta(days=1)).count() >= MAX_REPORTS_PER_DAY:
            messages.error(request, "Trop de signalements aujourd'hui. Réessayez demain.")
            return redirect(prop.get_absolute_url())
        else:
            report = ListingReport.objects.create(property=prop, reporter=request.user, reason=reason,
                                                  details=request.POST.get("details", "")[:2000])
            for admin_user in User.objects.filter(role=User.Role.ADMIN, is_active=True):
                Notification.objects.create(user=admin_user, title="Annonce signalée",
                                            message=f"{prop.title} — {report.get_reason_display()}",
                                            notification_type="systeme",
                                            link=f"/dashboard/admin-panel/signalements/{report.pk}/")
            messages.success(request, "Merci. Votre signalement a été transmis à l'équipe DOMIORA.")
            return redirect(prop.get_absolute_url())
    return render(request, "moderation/report_form.html", {"property": prop, "reasons": ListingReport.Reason.choices})


@role_required(User.Role.ADMIN)
def admin_reports(request):
    reports = ListingReport.objects.select_related("property", "reporter")
    status = request.GET.get("status", "open")
    if status != "all":
        reports = reports.filter(status=status)
    return render(request, "moderation/admin_list.html", {
        "page_obj": Paginator(reports, 20).get_page(request.GET.get("page")), "status_filter": status,
        "statuses": ListingReport.Status.choices, "dash_role": "admin", "active": "listing_reports",
    })


@role_required(User.Role.ADMIN)
def admin_report_detail(request, pk):
    report = get_object_or_404(ListingReport.objects.select_related("property", "property__owner", "reporter"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in ("reviewing", "dismissed", "action_taken"):
            messages.error(request, "Action inconnue.")
            return redirect("dashboard:admin_listing_report", pk=pk)
        report.status = action
        report.admin_note = request.POST.get("admin_note", "")
        report.handled_by = request.user
        report.handled_at = timezone.now()
        if action == "action_taken" and request.POST.get("unpublish") == "on":
            Property.objects.filter(pk=report.property_id).update(is_published=False)
            report.listing_unpublished = True
        report.save()
        messages.success(request, "Signalement mis à jour.")
        return redirect("dashboard:admin_listing_report", pk=pk)
    others = ListingReport.objects.filter(property=report.property).exclude(pk=report.pk)
    return render(request, "moderation/admin_detail.html", {
        "report": report, "others": others, "dash_role": "admin", "active": "listing_reports"})
