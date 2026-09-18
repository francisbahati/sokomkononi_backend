from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from rest_framework import permissions, viewsets

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import Category
from .serializers import CategorySerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


@extend_schema_view(
    list=extend_schema(
        summary="Orodha ya makundi",
        responses=CategorySerializer(many=True),
    ),
    retrieve=extend_schema(summary="Taarifa za kundi"),
    create=extend_schema(summary="Unda kundi"),
    update=extend_schema(summary="Badilisha kundi"),
    partial_update=extend_schema(summary="Sasisha sehemu ya kundi"),
    destroy=extend_schema(
        summary="Futa kundi",
        responses={
            204: OpenApiResponse(description="Kundi limewekwa kwenye kikapu."),
        },
    ),
)
class CategoryViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    staff_can_restore_any = True

    def get_queryset(self):
        qs = Category.objects.all()
        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return qs
        return qs.filter(is_active=True)

    def _can_restore(self, instance):
        return bool(self.request.user.is_staff)