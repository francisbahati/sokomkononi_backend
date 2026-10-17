from rest_framework import serializers

from apps.listings.models import Listing

from .models import SavedListing


class SavedListingListingSerializer(serializers.ModelSerializer):
    """Compact listing shape embedded in saved-listing responses."""

    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "price",
            "location",
            "status",
            "is_boosted",
            "is_featured",
            "primary_image",
            "category_name",
            "created_at",
        ]

    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first()
        if not image:
            image = obj.images.order_by("ordering", "created_at").first()
        if not image:
            return None
        request = self.context.get("request")
        for attr in ("card", "detail", "image"):
            f = getattr(image, attr, None)
            if f:
                try:
                    url = f.url
                    return request.build_absolute_uri(url) if request else url
                except Exception:
                    continue
        return None


class SavedListingSerializer(serializers.ModelSerializer):
    listing = SavedListingListingSerializer(read_only=True)

    class Meta:
        model = SavedListing
        fields = [
            "id",
            "listing",
            "snapshot_price",
            "snapshot_status",
            "saved_at",
        ]
        read_only_fields = fields


from apps.listings.ownership import PUBLIC_STATUSES


class SavedListingCreateSerializer(serializers.Serializer):
    listing = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.filter(status__in=PUBLIC_STATUSES),
    )