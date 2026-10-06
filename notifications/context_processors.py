from django.db.models import Q


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {"unread_notifications_count": 0}

    dash_role = request.session.get("dash_role")
    qs = request.user.notifications.filter(is_read=False)

    if dash_role == "client":
        qs = qs.filter(
            Q(link__startswith="/dashboard/client/") | Q(link="")
        ).exclude(link__startswith="/dashboard/admin-panel/")
    elif dash_role == "owner":
        qs = qs.filter(
            Q(link__startswith="/dashboard/proprietaire/") | Q(link="")
        ).exclude(link__startswith="/dashboard/admin-panel/")
    else:
        # admin or no role: exclude nothing extra
        pass

    return {"unread_notifications_count": qs.count()}
