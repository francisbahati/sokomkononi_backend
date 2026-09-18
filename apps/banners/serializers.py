from rest_framework import serializers

from .models import BannerAd


class BannerAdSerializer(serializers.ModelSerializer):
    listingId = serializers.IntegerField(source="listing_id", read_only=True)
    listingTitle = serializers.CharField(source="listing_title", read_only=True)
    sellerName = serializers.CharField(source="seller_name", read_only=True)

    class Meta:
        model = BannerAd
        fields = [
            "id", "listingId", "listingTitle",
            "category", "location", "price", "sellerName",
            "amount", "payment_reference",
            "active", "created_at", "expires_at",
        ]
        read_only_fields = fields


class BannerAdCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField()
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
