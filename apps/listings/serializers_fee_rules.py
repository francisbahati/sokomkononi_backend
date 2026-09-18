from rest_framework import serializers

from .models import ListingFeeRule


class ListingFeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingFeeRule
        fields = [
            "id", "name", "min_price", "max_price", "percentage",
            "is_active", "priority", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Jina linahitajika.")

        qs = ListingFeeRule.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Kiwango chenye jina hili tayari kipo."
            )
        return value

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