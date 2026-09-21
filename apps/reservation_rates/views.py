from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import ReservationRate
from .serializers import ReservationRateSerializer


class ReservationRateViewSet(viewsets.GenericViewSet):
    """
        GET     /api/reservation-rates/            public read
        PATCH   /api/reservation-rates/{tier}/     admin update
    """

    serializer_class = ReservationRateSerializer

    def get_permissions(self):
        if self.action == "list":
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request):
        qs = ReservationRate.objects.all()
        return Response(ReservationRateSerializer(qs, many=True).data)

    def partial_update(self, request, pk=None):
        obj = ReservationRate.objects.filter(tier=pk).first()
        if not obj and str(pk).isdigit():
            obj = ReservationRate.objects.filter(pk=int(pk)).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data or {}
        allowed = {
            "fee", "hours", "label_sw", "label_en",
            "sub_sw", "sub_en", "ordering",
        }
        updates = []
        for field in allowed:
            if field in data:
                setattr(obj, field, data[field])
                updates.append(field)
        if updates:
            obj.save(update_fields=updates)
        return Response(ReservationRateSerializer(obj).data)
