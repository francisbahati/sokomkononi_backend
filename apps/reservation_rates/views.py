# apps/reservation_rates/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny

from .models import ReservationRate
from .serializers import ReservationRateSerializer


class ReservationRateViewSet(viewsets.GenericViewSet):
    """
    Singleton viewset — ReservationRate moja (pk=1).

    GET     /api/reservation-rates/          → rate (object)
    PATCH   /api/reservation-rates/          → update rate
    POST    /api/reservation-rates/toggle/   → toggle is_enabled
    """
    serializer_class = ReservationRateSerializer
    queryset = ReservationRate.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_object(self):
        obj, _ = ReservationRate.objects.get_or_create(
            pk=1,
            defaults={
                "flat_fee": 50000,
                "days": 3,
                "is_enabled": True,
            },
        )
        return obj

    def list(self, request):
        return Response(ReservationRateSerializer(self.get_object()).data)

    def retrieve(self, request, pk=None):
        return Response(ReservationRateSerializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        obj = self.get_object()
        serializer = ReservationRateSerializer(
            obj, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle(self, request):
        obj = self.get_object()
        obj.is_enabled = not obj.is_enabled
        obj.save(update_fields=["is_enabled", "updated_at"])
        return Response({"is_enabled": obj.is_enabled})