# apps/reservation_rates/serializers.py
from rest_framework import serializers

from .models import ReservationSettings, ReservationTier


class ReservationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationSettings
        fields = ["id", "is_enabled", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class ReservationTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationTier
        fields = [
            "id",
            "hours",
            "fee",
            "is_active",
            "order",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate_hours(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Hours lazima iwe angalau 1."
            )
        if value > 8760:  # mwaka mmoja
            raise serializers.ValidationError(
                "Hours haiwezi kuzidi 8760 (mwaka mmoja)."
            )
        return value

    def validate_fee(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Fee haiwezi kuwa negative."
            )
        return value