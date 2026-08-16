def user_dash_role(request):
    """
    Injects `dash_role` into every template context.
    - Dashboard pages: determined by URL prefix (handled cleanly by DashboardRoleMiddleware).
    - Global pages (notifications, messages, profile...): determined by the session to maintain continuity.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        logger.info(f"User not authenticated, returning empty dash_role")
        return {}

    from accounts.models import User

    role = getattr(request.user, "role", User.Role.CLIENT)
    is_superuser = getattr(request.user, "is_superuser", False)

    current_path = request.path
    logger.info(f"Context processor: User={request.user.username}, Path={current_path}, Role={role}, Session dash_role={request.session.get('dash_role')}")

    # 1. Direct URL check (just in case the middleware hasn't run or is bypassed)
    if current_path.startswith('/dashboard/proprietaire/'):
        logger.info(f"Returning dash_role='owner' from URL")
        return {"dash_role": "owner"}
    elif current_path.startswith('/dashboard/admin-panel/'):
        logger.info(f"Returning dash_role='admin' from URL")
        return {"dash_role": "admin"}
    elif current_path.startswith('/dashboard/client/'):
        logger.info(f"Returning dash_role='client' from URL")
        return {"dash_role": "client"}
        
    # 2. For global pages, use the session to remember which dashboard they were on.
    dash_role = request.session.get('dash_role')
    if not dash_role:
        if role == User.Role.ADMIN or is_superuser:
            dash_role = "admin"
        elif role == User.Role.OWNER or role == User.Role.AGENT:
            dash_role = "owner"  # Owners and agents use owner dashboard
        else:
            # CLIENT and BUYER both use client dashboard
            dash_role = "client"
        logger.info(f"No session dash_role, defaulting to '{dash_role}' based on user role")

    logger.info(f"Returning dash_role='{dash_role}'")
    return {"dash_role": dash_role}
