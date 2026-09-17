from rest_framework import permissions, viewsets

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import ListingFeeRule
from .serializers_fee_rules import ListingFeeRuleSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Anyone can list/retrieve active fee rules.
    Only staff can create, update, or delete.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class ListingFeeRuleViewSet(
    SoftDeleteViewSetMixin,
    viewsets.ModelViewSet,
):
    """
    CRUD for ListingFeeRule.

    GET  /api/listings/fee-rules/          — list (active + inactive for staff)
    GET  /api/listings/fee-rules/<id>/     — retrieve one
    POST /api/listings/fee-rules/          — create (staff only)
    PUT/PATCH /api/listings/fee-rules/<id>/ — update (staff only)
    DELETE /api/listings/fee-rules/<id>/   — soft delete (staff only)

    Trash:
    GET  /api/listings/fee-rules/trash/
    POST /api/listings/fee-rules/<id>/restore/
    """

    serializer_class = ListingFeeRuleSerializer
    permission_classes = [IsAdminOrReadOnly]
    owner_field = "id"  # unused; only staff restore
    staff_can_restore_any = True

    def get_queryset(self):
        queryset = ListingFeeRule.objects.all()

        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return queryset.order_by("priority", "min_price")

        return queryset.filter(is_active=True).order_by(
            "priority", "min_price"
        )

    def _can_restore(self, instance):
        return bool(
            self.request.user.is_authenticated
            and self.request.user.is_staff
        )