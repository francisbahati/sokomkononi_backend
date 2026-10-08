# apps/leading_fees/serializers.py
from rest_framework import serializers

from .models import LeadingFeeConfig, LeadingPackage, ListingLeading


class LeadingFeeConfigSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    desc = serializers.SerializerMethodField()

    class Meta:
        model = LeadingFeeConfig
        fields = ["id", "is_enabled", "label", "desc", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def get_label(self, obj):
        return {"sw": obj.label_sw, "en": obj.label_en}

    def get_desc(self, obj):
        return {"sw": obj.desc_sw, "en": obj.desc_en}


class LeadingPackageSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    pricing = serializers.SerializerMethodField()

    class Meta:
        model = LeadingPackage
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
            return calculate_promotion_price(obj.price, "LEADING")
        except Exception:
            return None


class ListingLeadingSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    package_name = serializers.CharField(source="package.name", read_only=True)

    class Meta:
        model = ListingLeading
        fields = [
            "id", "listing", "listing_title", "seller", "seller_name",
            "package", "package_name",
            "days", "price", "payment_status", "payment_reference",
            "paid_at", "status", "starts_at", "expires_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class LeadingApplySerializer(serializers.Serializer):
    listing = serializers.IntegerField()
    package = serializers.IntegerField(required=True)
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )


class LeadingPaymentSerializer(serializers.Serializer):
    payment_reference = serializers.CharField(max_length=255)