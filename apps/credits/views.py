from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UserCredit, UserService
from .serializers import (
    ConsumeCreditSerializer,
    UserCreditSerializer,
    UserServiceSerializer,
)
from .services import consume_credit, get_credit, has_service


class UserCreditViewSet(viewsets.GenericViewSet):
    serializer_class = UserCreditSerializer
    """
        GET     /api/credits/                my credits (dict summary)
        GET     /api/credits/all/            flat list
        POST    /api/credits/consume/        { service_key, amount }
    """

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        qs = UserCredit.objects.filter(user=request.user)
        return Response(UserCreditSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="all")
    def all_flat(self, request):
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

    @action(detail=False, methods=["post"], url_path="consume")
    def consume(self, request):
        serializer = ConsumeCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credit = consume_credit(
            user=request.user,
            service_key=serializer.validated_data["service_key"],
            amount=serializer.validated_data["amount"],
        )
        return Response(UserCreditSerializer(credit).data)
