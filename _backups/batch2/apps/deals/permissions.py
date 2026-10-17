from rest_framework import permissions


class IsDealParticipant(permissions.BasePermission):
    """
    Ruhusa ya buyer au seller pekee kufikia Deal Room.

    Admin anaweza kufikia Deal Room kwa ajili ya
    moderation/dispute management.
    """

    message = (
        "Huruhusiwi kufikia Deal Room hii. "
        "Ni mnunuzi, muuzaji, au admin pekee."
    )

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff:
            return True

        return request.user.id in [
            obj.buyer_id,
            obj.seller_id,
        ]


class IsDealParticipantOrReadOnly(permissions.BasePermission):
    """
    Buyer na seller wanaweza kusoma Deal Room.
    Admin anaweza kusoma.
    """

    message = (
        "Huruhusiwi kufikia taarifa za Deal Room hii."
    )

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff:
            return True

        return request.user.id in [
            obj.buyer_id,
            obj.seller_id,
        ]


class IsVerifiedDealUser(permissions.BasePermission):
    """
    Buyer/seller lazima awe active na verified
    kabla ya kufanya vitendo kwenye Deal Room.
    """

    message = (
        "Akaunti yako lazima iwe imethibitishwa "
        "na iwe active ili kutumia Deal Room."
    )

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_verified
        )