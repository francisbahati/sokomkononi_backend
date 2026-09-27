"""Shared permission classes. Import these instead of redefining."""
from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsVerifiedUser(permissions.BasePermission):
    message = (
        "Akaunti yako lazima iwe active na imethibitishwa."
    )

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and u.is_active and u.is_verified
        )
