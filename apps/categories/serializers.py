from rest_framework import serializers

from .models import Category
from . import stats


class CategorySerializer(serializers.ModelSerializer):
    # A normal URL. Binary uploads use POST /api/categories/upload-image/.
    image_url = serializers.URLField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )

    # Idadi ya listings (zisizofutwa, status zote). Staff pekee.
    listings_count = serializers.SerializerMethodField()

    def get_listings_count(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_staff):
            return None
        annotated = getattr(obj, "listings_count_annotated", None)
        if annotated is None:
            annotated = obj.__dict__.get("listings_count")
        if annotated is not None:
            return annotated
        return stats.count_for(obj.pk)

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
            "listings_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]
