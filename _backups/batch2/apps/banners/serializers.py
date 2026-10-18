# apps/banners/serializers.py
from rest_framework import serializers

from .models import BannerAd, Campaign


class BannerAdSerializer(serializers.ModelSerializer):
    listingId = serializers.IntegerField(source="listing_id", read_only=True)
    listingTitle = serializers.CharField(source="listing_title", read_only=True)
    sellerName = serializers.CharField(source="seller_name", read_only=True)
    package_name = serializers.CharField(source="package.name", read_only=True)
    package_hours = serializers.IntegerField(
        source="package.duration_hours", read_only=True, allow_null=True,
    )

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


class BannerAdCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField()
    package = serializers.IntegerField(required=True)
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )

    def validate_package(self, value):
        from apps.advertisement_fees.models import AdvertisementPackage
        pkg = AdvertisementPackage.objects.filter(
            pk=value, is_active=True,
        ).first()
        if not pkg:
            raise serializers.ValidationError(
                "Advertisement package haipo active."
            )
        return pkg


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
            # Convert string to bilingual
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