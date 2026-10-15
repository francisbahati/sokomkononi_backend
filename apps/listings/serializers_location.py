"""Location + multipart create serializers for Listing."""
from decimal import Decimal

from rest_framework import serializers

from apps.categories.models import Category

from .models import Listing, ListingImage


class LocationUpdateSerializer(serializers.Serializer):
    """PATCH /api/listings/{id}/location/"""

    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        required=False,
        allow_null=True,
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
        required=False,
        allow_null=True,
    )
    location = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
    address_text = serializers.CharField(
        max_length=500, required=False, allow_blank=True,
    )

    def validate(self, attrs):
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lng = attrs.get("longitude", getattr(self.instance, "longitude", None))

        if (lat is None) != (lng is None):
            raise serializers.ValidationError({
                "latitude": "Latitude na longitude lazima ziwe zote au zote tupu.",
                "longitude": "Latitude na longitude lazima ziwe zote au zote tupu.",
            })
        return attrs


class ListingCreateWithImagesSerializer(serializers.Serializer):
    """
    Multipart serializer used when creating a listing with images
    in a single POST.

    Accepts:
        - All standard listing fields (form-data)
        - `images` = array of files (up to 10)
        - `attributes` = JSON string (parsed internally)
    """

    MAX_IMAGES = 10
    MAX_IMAGE_BYTES = 5 * 1024 * 1024

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
    )
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    price = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("0"))
    location = serializers.CharField(max_length=255)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        min_value=Decimal("-90"), max_value=Decimal("90"),
        required=False, allow_null=True,
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        min_value=Decimal("-180"), max_value=Decimal("180"),
        required=False, allow_null=True,
    )
    address_text = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default="",
    )
    attributes = serializers.JSONField(required=False, default=dict)

    def validate_title(self, value):
        value = (value or "").strip()
        if len(value) < 5:
            raise serializers.ValidationError(
                "Jina la tangazo lazima liwe na angalau herufi 5."
            )
        return value

    def validate_description(self, value):
        value = (value or "").strip()
        if len(value) < 20:
            raise serializers.ValidationError(
                "Maelezo lazima yawe na angalau herufi 20."
            )
        return value

    def validate_location(self, value):
        value = (value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Tafadhali weka eneo sahihi."
            )
        return value

    def validate(self, attrs):
        lat = attrs.get("latitude")
        lng = attrs.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError({
                "latitude": "Latitude na longitude lazima ziwe zote mbili.",
            })

        # Parse `attributes` if it arrived as a JSON string
        attrs_raw = attrs.get("attributes")
        if isinstance(attrs_raw, str):
            import json
            try:
                attrs["attributes"] = json.loads(attrs_raw) if attrs_raw else {}
            except Exception:
                raise serializers.ValidationError({
                    "attributes": "attributes lazima iwe JSON sahihi.",
                })
        if not isinstance(attrs["attributes"], dict):
            raise serializers.ValidationError({
                "attributes": "attributes lazima iwe JSON object.",
            })

        return attrs
