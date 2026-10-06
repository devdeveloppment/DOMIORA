from django.shortcuts import redirect

class DashboardRoleMiddleware:
    """
    Middleware permettant de mémoriser le rôle actif du tableau de bord dans la session
    selon le préfixe de l'URL.

    Cela permet, lorsque l'utilisateur navigue sur des pages globales comme le profil ou
    les notifications, au processeur de contexte de savoir quel menu latéral afficher.
    Le middleware applique aussi un contrôle d'accès basé sur les rôles pour empêcher
    toute traversée entre les espaces d'un rôle et d'un autre.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        import logging
        self.logger = logging.getLogger(__name__)

    def __call__(self, request):
        # Vérifie si l'utilisateur est connecté avant d'appliquer les règles de rôle.
        if request.user.is_authenticated:
            from accounts.models import User
            current_path = request.path

            # Journalisation utile pour suivre les accès dashboard et la session active.
            self.logger.info(f"Utilisateur authentifié: {request.user.username}, chemin: {current_path}, clé de session: {request.session.session_key}")

            # Contrôle d'accès par rôle selon le chemin courant.
            if current_path.startswith('/dashboard/admin-panel/'):
                # Seuls les administrateurs peuvent accéder au panneau d'administration.
                if not (request.user.is_superuser or request.user.role == User.Role.ADMIN):
                    from django.contrib import messages
                    messages.error(request, "Accès refusé. Cette zone est réservée aux administrateurs.")
                    return redirect("accounts:login")

            elif current_path.startswith('/dashboard/proprietaire/'):
                # Seuls les propriétaires peuvent accéder au tableau de bord propriétaire.
                if not request.user.role == User.Role.OWNER:
                    from django.contrib import messages
                    messages.error(request, "Accès refusé. Cette zone est réservée aux propriétaires.")
                    return redirect("accounts:login")

            elif current_path.startswith('/dashboard/client/'):
                # L'accès au tableau de bord client est autorisé pour les utilisateurs authentifiés.
                # La vérification spécifique du paiement est gérée ailleurs par le statut "has_unlocked".
                pass

            # Enregistre le rôle courant dans la session pour les pages globales du dashboard.
            if current_path.startswith('/dashboard/proprietaire/'):
                if request.session.get('dash_role') != 'owner':
                    request.session['dash_role'] = 'owner'
                    self.logger.info(f"Rôle de session défini sur 'owner' pour l'utilisateur {request.user.username}")
            elif current_path.startswith('/dashboard/admin-panel/'):
                if request.session.get('dash_role') != 'admin':
                    request.session['dash_role'] = 'admin'
                    self.logger.info(f"Rôle de session défini sur 'admin' pour l'utilisateur {request.user.username}")
            elif current_path.startswith('/dashboard/client/'):
                if request.session.get('dash_role') != 'client':
                    request.session['dash_role'] = 'client'
                    self.logger.info(f"Rôle de session défini sur 'client' pour l'utilisateur {request.user.username}")

        response = self.get_response(request)
        return response
