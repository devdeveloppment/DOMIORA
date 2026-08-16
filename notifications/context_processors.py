def unread_notifications(request):
    if request.user.is_authenticated:
        qs = request.user.notifications.filter(is_read=False)
        
        # Determine current dash_role to exclude admin notifications from client/owner dashboards
        dash_role = request.session.get("dash_role")
        
        # If the user is currently browsing the client or owner dashboard,
        # hide admin-specific notifications from the counter to prevent confusion.
        if dash_role in ["client", "owner"]:
            qs = qs.exclude(link__startswith="/dashboard/admin-panel/")
            
        count = qs.count()
        return {"unread_notifications_count": count}
    return {"unread_notifications_count": 0}
