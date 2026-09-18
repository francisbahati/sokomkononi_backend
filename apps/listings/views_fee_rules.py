from rest_framework import permissions, viewsets

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import ListingFeeRule
from .serializers_fee_rules import ListingFeeRuleSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class ListingFeeRuleViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ListingFeeRuleSerializer
    permission_classes = [IsAdminOrReadOnly]
    staff_can_restore_any = True

    def get_queryset(self):
        qs = ListingFeeRule.objects.all()
        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return qs.order_by("priority", "min_price")
        return qs.filter(is_active=True).order_by("priority", "min_price")

    def _can_restore(self, instance):
        return bool(
            self.request.user.is_authenticated
            and self.request.user.is_staff
        )