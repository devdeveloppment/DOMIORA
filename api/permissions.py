from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "client", None)
        return owner == request.user or request.user.is_superuser


class IsAgentOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        agent = getattr(obj, "agent", None)
        return (agent and agent.user == request.user) or request.user.is_superuser
