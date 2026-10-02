# apps/advertisement_fees/views.py
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AdvertisementFeeConfig
from .serializers import AdvertisementFeeConfigSerializer


class AdvertisementFeeConfigViewSet(viewsets.GenericViewSet):
    serializer_class = AdvertisementFeeConfigSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request):
        obj, _ = AdvertisementFeeConfig.objects.get_or_create(pk=1)
        return Response(AdvertisementFeeConfigSerializer(obj).data)

    def create(self, request):
        obj, _ = AdvertisementFeeConfig.objects.get_or_create(pk=1)
        serializer = AdvertisementFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request):
        obj, _ = AdvertisementFeeConfig.objects.get_or_create(pk=1)
        serializer = AdvertisementFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # ═══════════════════════════════════════════════════════════
    # TOGGLE — POST /api/advertisement-fees/toggle/
    # ═══════════════════════════════════════════════════════════
    @action(
        detail=False,
        methods=["post"],
        url_path="toggle",
        permission_classes=[permissions.IsAdminUser],
    )
    def toggle(self, request):
        obj, _ = AdvertisementFeeConfig.objects.get_or_create(pk=1)
        obj.is_enabled = not obj.is_enabled
        obj.save(update_fields=["is_enabled", "updated_at"])
        return Response({"is_enabled": obj.is_enabled})