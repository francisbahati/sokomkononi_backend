# apps/listings/serializers_fee_rules.py
from decimal import Decimal

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
    # ✅ FIX: Tumia SerializerMethodField ili kurudisha slug kila mara
    # (kutoka category FK au category_slug legacy field)
    category_slug = serializers.SerializerMethodField()

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

    def get_category_slug(self, obj):
        """
        Return slug kutoka category FK ikiwa ipo, vinginevyo
        tumia `category_slug` (legacy field).
        Hii inahakikisha frontend inapata slug kila mara.
        """
        if not obj:
            return ""
        if obj.category_id and obj.category:
            return obj.category.slug or ""
        return obj.category_slug or ""

    def validate(self, attrs):
        fee_mode = (attrs.get("fee_mode") or "").upper()
        flat_fee = attrs.get("flat_fee")
        percentage = attrs.get("percentage")
        instance = getattr(self, "instance", None)

        # When updating, fall back to the instance's current values for
        # fields not included in the payload.
        if instance is not None:
            if flat_fee is None:
                flat_fee = instance.flat_fee
            if percentage is None:
                percentage = instance.percentage
            if not fee_mode:
                fee_mode = (instance.fee_mode or "").upper()

        # Default to FLAT if fee_mode not provided
        if not fee_mode:
            fee_mode = "FLAT"

        # Enforce a positive fee for the active mode.
        if fee_mode == "FLAT":
            try:
                flat_val = Decimal(str(flat_fee or 0))
            except Exception:
                raise serializers.ValidationError({
                    "flat_fee": "Ada si sahihi."
                })
            if flat_val <= 0:
                raise serializers.ValidationError({
                    "flat_fee": (
                        "Ada lazima iwe kubwa kuliko sifuri. "
                        "Kila listing inatozwa ada."
                    )
                })
        elif fee_mode == "PERCENTAGE":
            try:
                pct_val = Decimal(str(percentage or 0))
            except Exception:
                raise serializers.ValidationError({
                    "percentage": "Asilimia si sahihi."
                })
            if pct_val <= 0:
                raise serializers.ValidationError({
                    "percentage": (
                        "Asilimia lazima iwe kubwa kuliko sifuri. "
                        "Kila listing inatozwa ada."
                    )
                })

        # Ensure category is set when creating
        if instance is None and not attrs.get("category"):
            raise serializers.ValidationError({
                "category": "Category inahitajika."
            })

        return attrs

    def _ensure_category_slug(self, validated_data, instance=None):
        category = validated_data.get("category")
        # If `category` (FK id) is supplied, mirror it to category_slug.
        # `category_slug` is read_only in serializer output, but we set it
        # directly on the model so it lands in the DB (legacy compat).
        if category is not None:
            validated_data["category_slug"] = category.slug
            return validated_data

        if instance is not None and instance.category is not None:
            validated_data["category_slug"] = instance.category.slug
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