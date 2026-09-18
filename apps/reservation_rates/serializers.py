from rest_framework import serializers

from .models import ReservationRate


class ReservationRateSerializer(serializers.ModelSerializer):
    id_field = serializers.CharField(source="tier", read_only=True)
    label = serializers.SerializerMethodField()
    sub = serializers.SerializerMethodField()

    class Meta:
        model = ReservationRate
        fields = [
            "id_field", "tier", "hours",
            "label", "sub", "fee", "ordering",
        ]

    def get_label(self, obj):
        return {"sw": obj.label_sw, "en": obj.label_en}

    def get_sub(self, obj):
        if not obj.sub_sw and not obj.sub_en:
            return None
        return {"sw": obj.sub_sw, "en": obj.sub_en}
