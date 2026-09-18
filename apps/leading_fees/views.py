from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import LeadingFeeConfig
from .serializers import LeadingFeeConfigSerializer


class LeadingFeeConfigViewSet(viewsets.GenericViewSet):
    """
        GET     /api/leading-fees/       public read
        POST    /api/leading-fees/       admin upsert
        PATCH   /api/leading-fees/       admin partial
    """

    serializer_class = LeadingFeeConfigSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        return Response(LeadingFeeConfigSerializer(obj).data)

    def create(self, request):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        serializer = LeadingFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        serializer = LeadingFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
