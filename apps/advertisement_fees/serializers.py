# apps/advertisement_fees/serializers.py
from rest_framework import serializers

from .models import AdvertisementFeeConfig, AdvertisementPackage


class AdvertisementFeeConfigSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    desc = serializers.SerializerMethodField()

    class Meta:
        model = AdvertisementFeeConfig
        fields = ["id", "is_enabled", "label", "desc", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def get_label(self, obj):
        return {"sw": obj.label_sw, "en": obj.label_en}

    def get_desc(self, obj):
        return {"sw": obj.desc_sw, "en": obj.desc_en}


class AdvertisementPackageSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    pricing = serializers.SerializerMethodField()

    class Meta:
        model = AdvertisementPackage
        fields = [
            "id", "name", "duration_hours", "duration_days",
            "price", "pricing", "description", "is_active", "ordering",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "duration_days", "pricing", "created_at", "updated_at"]

    def get_duration_days(self, obj):
        return obj.duration_hours / 24

    def get_pricing(self, obj):
        try:
            from apps.banners.services import calculate_promotion_price
            return calculate_promotion_price(obj.price, "ADVERTISEMENT")
        except Exception:
            return None