from rest_framework import permissions, viewsets
from rest_framework.response import Response

from .models import ReservationRate
from .serializers import ReservationRateSerializer


class ReservationRateViewSet(viewsets.GenericViewSet):
    """
        GET     /api/reservation-rates/       public read
        POST    /api/reservation-rates/{tier}/  admin update fee
    """

    serializer_class = ReservationRateSerializer

    def get_permissions(self):
        if self.action == "list":
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request):
        qs = ReservationRate.objects.all()
        return Response(ReservationRateSerializer(qs, many=True).data)
