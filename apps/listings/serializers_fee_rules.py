from rest_framework import serializers

from .models import ListingFeeRule


class ListingFeeRuleSerializer(serializers.ModelSerializer):
    """
    Serializer for the fee rule used to compute the Listing Fee.

    The frontend uses `name` as the category key (e.g. "nyumba",
    "viwanja"), so admin must name rules after the category keys
    they apply to.
    """

    class Meta:
        model = ListingFeeRule

        fields = [
            "id",
            "name",
            "min_price",
            "max_price",
            "percentage",
            "is_active",
            "priority",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        min_price = attrs.get(
            "min_price",
            getattr(self.instance, "min_price", 0),
        )
        max_price = attrs.get(
            "max_price",
            getattr(self.instance, "max_price", None),
        )

        if max_price is not None and max_price < min_price:
            raise serializers.ValidationError({
                "max_price": (
                    "Bei ya juu haiwezi kuwa chini ya bei ya chini."
                )
            })

        percentage = attrs.get(
            "percentage",
            getattr(self.instance, "percentage", None),
        )

        if percentage is not None and percentage <= 0:
            raise serializers.ValidationError({
                "percentage": (
                    "Asilimia lazima iwe kubwa kuliko sifuri."
                )
            })

        return attrs