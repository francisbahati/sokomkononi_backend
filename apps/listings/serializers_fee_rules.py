# apps/listings/serializers_fee_rules.py
from django.utils.text import slugify
from rest_framework import serializers

from apps.categories.models import Category

from .models import ListingFeeRule


class ListingFeeRuleSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False,
        allow_null=True,
    )
    category_name = serializers.CharField(
        source="category.name", read_only=True, allow_null=True,
    )
    category_slug = serializers.CharField(
        source="category.slug", read_only=True,
        allow_null=True, required=False,
    )

    class Meta:
        model = ListingFeeRule
        fields = [
            "id",
            "category",
            "category_name",
            "category_slug",
            "name",
            "percentage",
            "min_price",
            "max_price",
            "flat_fee",
            "fee_mode",
            "is_active",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "category_name", "category_slug",
            "created_at", "updated_at",
        ]

    def _ensure_category_slug(self, validated_data, instance=None):
        category = validated_data.get("category")
        # If `category` (FK id) is supplied, always mirror it to category_slug.
        if category is not None:
            validated_data["category_slug"] = category.slug
            return validated_data

        if not validated_data.get("category_slug"):
            name = validated_data.get("name") or (
                instance.name if instance else ""
            )
            if name:
                validated_data["category_slug"] = slugify(name)
        return validated_data

    def create(self, validated_data):
        return super().create(self._ensure_category_slug(validated_data))

    def update(self, instance, validated_data):
        return super().update(
            instance,
            self._ensure_category_slug(validated_data, instance),
        )
