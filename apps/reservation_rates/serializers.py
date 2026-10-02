# apps/reservation_rates/serializers.py
from rest_framework import serializers

from .models import ReservationRate


class ReservationRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationRate
        fields = [
            "id",
            "flat_fee",
            "days",
            "is_enabled",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]