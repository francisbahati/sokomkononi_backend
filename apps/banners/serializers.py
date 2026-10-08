# apps/banners/serializers.py
from rest_framework import serializers

from .models import BannerAd


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