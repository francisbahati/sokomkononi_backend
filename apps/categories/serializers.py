from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    # Accept both a normal URL and a data: base64 payload.
    image_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5_000_000,
    )

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon_key",
            "image_url",
            "is_popular",
            "extra",
            "is_active",
            "ordering",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]
