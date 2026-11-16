"""Shared permission classes. Import these instead of redefining."""
from rest_framework import permissions

from .admin_2fa import IsAdminWith2FA, admin_2fa_failure


class IsAdminUser(IsAdminWith2FA):
    """Staff + 2FA iliyowashwa (angalia apps/core/admin_2fa.py)."""


class IsSuperUser(permissions.BasePermission):
    """Superuser + 2FA iliyowashwa."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_superuser):
            return False
        failure = admin_2fa_failure(request)
        if failure:
            self.code, self.message = failure
            return False
        return True


class IsAdminOrReadOnly(permissions.BasePermission):
    """Kusoma: wote. Kuandika: staff + 2FA iliyowashwa."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not (user and user.is_authenticated and user.is_staff):
            return False
        failure = admin_2fa_failure(request)
        if failure:
            self.code, self.message = failure
            return False
        return True


class IsVerifiedUser(permissions.BasePermission):
    message = "Akaunti yako lazima iwe active na imethibitishwa."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_verified)
