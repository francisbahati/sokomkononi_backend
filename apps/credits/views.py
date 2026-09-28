from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UserCredit, UserService
from .serializers import (
    UserCreditSerializer,
    UserServiceSerializer,
)
from .services import has_service


class UserCreditViewSet(viewsets.GenericViewSet):
    """
    Public credit view — read-only. Internal services consume credits
    directly; there is NO public consume endpoint.
    """
    serializer_class = UserCreditSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        qs = UserCredit.objects.filter(user=request.user)
        return Response(UserCreditSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="services")
    def my_services(self, request):
        qs = UserService.objects.filter(user=request.user)
        return Response(UserServiceSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"has/(?P<service>[^/.]+)")
    def check_service(self, request, service=None):
        return Response({
            "service": service,
            "has": has_service(request.user, service),
        })
