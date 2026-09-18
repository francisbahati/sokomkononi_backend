from rest_framework import permissions, status, viewsets
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

    def partial_update(self, request, pk=None):
        obj, _ = AdvertisementFeeConfig.objects.get_or_create(pk=1)
        serializer = AdvertisementFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
