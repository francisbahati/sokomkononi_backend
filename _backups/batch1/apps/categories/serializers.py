from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    # A normal URL. Binary uploads use POST /api/categories/upload-image/.
    image_url = serializers.URLField(
        required=False,
        allow_blank=True,
        max_length=2000,
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
