# apps/reservation_rates/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny

from .models import ReservationSettings, ReservationTier
from .serializers import (
    ReservationSettingsSerializer,
    ReservationTierSerializer,
)


class ReservationSettingsViewSet(viewsets.GenericViewSet):
    """
    Singleton settings (is_enabled pekee).

    GET   /api/reservation-settings/          → { is_enabled, ... }
    PATCH /api/reservation-settings/          → update
    POST  /api/reservation-settings/toggle/   → toggle is_enabled
    """
    serializer_class = ReservationSettingsSerializer
    queryset = ReservationSettings.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_object(self):
        obj, _ = ReservationSettings.objects.get_or_create(pk=1)
        return obj

    def list(self, request):
        return Response(ReservationSettingsSerializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        obj = self.get_object()
        serializer = ReservationSettingsSerializer(
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


class ReservationTierViewSet(viewsets.ModelViewSet):
    """
    CRUD kwa reservation tiers.

    GET    /api/reservation-tiers/           → list
    POST   /api/reservation-tiers/           → create
    GET    /api/reservation-tiers/{id}/      → retrieve
    PATCH  /api/reservation-tiers/{id}/      → update
    DELETE /api/reservation-tiers/{id}/      → delete
    POST   /api/reservation-tiers/{id}/toggle/ → toggle is_active
    """
    serializer_class = ReservationTierSerializer
    queryset = ReservationTier.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        tier = self.get_object()
        tier.is_active = not tier.is_active
        tier.save(update_fields=["is_active", "updated_at"])
        return Response({"is_active": tier.is_active})