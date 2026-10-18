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

    For child objects without a direct `seller_id` (e.g. ListingImage),
    resolve ownership via the related `listing.seller_id`.
    """

    message = "Huna ruhusa ya kubadilisha tangazo ambalo si lako."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        seller_id = getattr(obj, "seller_id", None)
        if seller_id is None:
            listing = getattr(obj, "listing", None)
            if listing is not None:
                seller_id = getattr(listing, "seller_id", None)

        return seller_id == request.user.id
