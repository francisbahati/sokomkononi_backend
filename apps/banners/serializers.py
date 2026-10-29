# apps/banners/serializers.py
from rest_framework import serializers

from .models import BannerAd, Campaign


class BannerAdSerializer(serializers.ModelSerializer):
    listingId = serializers.IntegerField(source="listing_id", read_only=True)
    listingTitle = serializers.CharField(source="listing_title", read_only=True)
    sellerName = serializers.CharField(source="seller_name", read_only=True)
    package_name = serializers.SerializerMethodField()
    package_hours = serializers.SerializerMethodField()

    class Meta:
        model = BannerAd
        fields = [
            "id", "listingId", "listingTitle",
            "category", "location", "price", "sellerName",
            "package", "package_name", "package_hours",
            "amount", "payment_reference",
            "active", "created_at", "expires_at",
        ]
        read_only_fields = fields

    def get_package_name(self, obj):
        return obj.package.name if obj.package else None

    def get_package_hours(self, obj):
        return obj.package.duration_hours if obj.package else None


class BannerAdCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField()
    package = serializers.IntegerField(required=False, allow_null=True)
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )

    def validate_package(self, value):
        if value is None:
            return None
        from apps.advertisement_fees.models import AdvertisementPackage
        pkg = AdvertisementPackage.objects.filter(
            pk=value, is_active=True,
        ).first()
        if not pkg:
            raise serializers.ValidationError(
                "Advertisement package haipo active."
            )
        return pkg

    def validate(self, attrs):
        from apps.advertisement_fees.models import AdvertisementFeeConfig
        fee_enabled = AdvertisementFeeConfig.get_solo().is_enabled
        if fee_enabled and not attrs.get("package"):
            raise serializers.ValidationError({
                "package": ["Advertisement package inahitajika."],
            })
        return attrs


# ============================================================
# CAMPAIGN SERIALIZER
# ============================================================
class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            "id",
            "name", "description",
            "discount_percent",
            "applies_to",
            "type",
            "start_date", "end_date",
            "budget", "spent",
            "active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        if isinstance(value, str):
            value = {"sw": value, "en": value}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "name lazima iwe object {sw, en}."
            )
        if not (value.get("sw") or value.get("en")):
            raise serializers.ValidationError(
                "name haiwezi kuwa tupu."
            )
        return value

    def validate_description(self, value):
        if isinstance(value, str):
            value = {"sw": value, "en": value}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "description lazima iwe object {sw, en}."
            )
        return value

    def validate_discount_percent(self, value):
        v = float(value or 0)
        if v < 0 or v > 100:
            raise serializers.ValidationError(
                "Punguzo lazima liwe kati ya 0 na 100."
            )
        return value

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "Tarehe ya mwisho lazima iwe baada ya kuanza."}
            )
        return attrs