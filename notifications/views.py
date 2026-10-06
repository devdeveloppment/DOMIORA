from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    # dash_role is now provided by the context processor
    return render(request, "notifications/list.html", {"notifications": notifications, "active": "notifications"})


@login_required
def mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    # Redirect to dashboard if link is missing or invalid
    if notif.link:
        # Sync session dash_role based on the notification link target
        # so the user lands in the correct dashboard context
        link = notif.link
        if "/dashboard/client/" in link:
            request.session["dash_role"] = "client"
        elif "/dashboard/proprietaire/" in link:
            request.session["dash_role"] = "owner"
        elif "/dashboard/admin-panel/" in link:
            request.session["dash_role"] = "admin"
        return redirect(link)
    return redirect("notifications:list")


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications:list")
