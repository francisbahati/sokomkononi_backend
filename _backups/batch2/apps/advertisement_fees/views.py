# apps/advertisement_fees/views.py
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AdvertisementFeeConfig, AdvertisementPackage
from .serializers import (
    AdvertisementFeeConfigSerializer,
    AdvertisementPackageSerializer,
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


class AdvertisementFeeConfigViewSet(viewsets.GenericViewSet):
    serializer_class = AdvertisementFeeConfigSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request):
        obj = AdvertisementFeeConfig.get_solo()
        return Response(AdvertisementFeeConfigSerializer(obj).data)

    def create(self, request):
        obj = AdvertisementFeeConfig.get_solo()
        serializer = AdvertisementFeeConfigSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request):
        obj = AdvertisementFeeConfig.get_solo()
        serializer = AdvertisementFeeConfigSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="toggle", permission_classes=[permissions.IsAdminUser])
    def toggle(self, request):
        obj = AdvertisementFeeConfig.get_solo()
        obj.is_enabled = not obj.is_enabled
        obj.save(update_fields=["is_enabled", "updated_at"])
        return Response({"is_enabled": obj.is_enabled})


class AdvertisementPackageViewSet(viewsets.ModelViewSet):
    serializer_class = AdvertisementPackageSerializer
    permission_classes = [IsAdminOrReadOnly]
    queryset = AdvertisementPackage.objects.all()

    def get_queryset(self):
        qs = AdvertisementPackage.objects.all()
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        return qs.filter(is_active=True)

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        pkg = self.get_object()
        pkg.is_active = not pkg.is_active
        pkg.save(update_fields=["is_active", "updated_at"])
        return Response({"is_active": pkg.is_active})