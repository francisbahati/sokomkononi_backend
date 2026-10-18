from rest_framework import permissions


class IsVerifiedUser(permissions.BasePermission):
    """
    Only authenticated, active and verified users can create listings.
    """

    message = (
        "Ni watumiaji waliothibitishwa pekee wanaoweza kuweka matangazo."
    )

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.is_verified
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Admins can manage every listing.
    Normal users can only modify their own listings.
    """

    message = (
        "Huna ruhusa ya kubadilisha tangazo ambalo si lako."
    )

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        return obj.seller_id == request.user.id