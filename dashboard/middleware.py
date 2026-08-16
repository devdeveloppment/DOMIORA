class DashboardRoleMiddleware:
    """
    Middleware to track the active dashboard role in the session based on the URL prefix.
    This ensures that when a user navigates to global pages (like Profile or Notifications),
    the context processor knows which sidebar to render.
    Also enforces role-based access control to prevent cross-role access.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        import logging
        self.logger = logging.getLogger(__name__)

    def __call__(self, request):
        if request.user.is_authenticated:
            from accounts.models import User
            current_path = request.path
            
            self.logger.info(f"Authenticated user: {request.user.username}, Path: {current_path}, Session key: {request.session.session_key}")
            
            # Enforce role-based access control
            if current_path.startswith('/dashboard/admin-panel/'):
                # Only admins can access admin panel
                if not (request.user.is_superuser or request.user.role == User.Role.ADMIN):
                    from django.contrib import messages
                    messages.error(request, "Accès refusé. Cette zone est réservée aux administrateurs.")
                    return redirect("accounts:login")
                    
            elif current_path.startswith('/dashboard/proprietaire/'):
                # Only owners and agents can access owner dashboard
                if not (request.user.role == User.Role.OWNER or request.user.role == User.Role.AGENT):
                    from django.contrib import messages
                    messages.error(request, "Accès refusé. Cette zone est réservée aux propriétaires.")
                    return redirect("accounts:login")
                    
            elif current_path.startswith('/dashboard/client/'):
                # Only clients and buyers can access client dashboard
                if not (request.user.role == User.Role.CLIENT or request.user.role == User.Role.BUYER):
                    from django.contrib import messages
                    messages.error(request, "Accès refusé. Cette zone est réservée aux clients.")
                    return redirect("accounts:login")
            
            # Track dashboard role in session
            if current_path.startswith('/dashboard/proprietaire/'):
                if request.session.get('dash_role') != 'owner':
                    request.session['dash_role'] = 'owner'
                    self.logger.info(f"Set dash_role to 'owner' for user {request.user.username}")
            elif current_path.startswith('/dashboard/admin-panel/'):
                if request.session.get('dash_role') != 'admin':
                    request.session['dash_role'] = 'admin'
                    self.logger.info(f"Set dash_role to 'admin' for user {request.user.username}")
            elif current_path.startswith('/dashboard/client/'):
                if request.session.get('dash_role') != 'client':
                    request.session['dash_role'] = 'client'
                    self.logger.info(f"Set dash_role to 'client' for user {request.user.username}")
                    
        response = self.get_response(request)
        return response
