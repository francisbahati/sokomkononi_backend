from rest_framework import serializers

from .models import SavedSearch


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = [
            "id",
            "name",
            "query",
            "category_slug",
            "region",
            "min_price",
            "max_price",
            "verified_only",
            "match_count",
            "last_checked",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "match_count",
            "last_checked",
            "created_at",
        ]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Jina linahitajika.")
        return value

    def validate(self, attrs):
        min_price = attrs.get("min_price", getattr(self.instance, "min_price", None))
        max_price = attrs.get("max_price", getattr(self.instance, "max_price", None))
        if min_price is not None and max_price is not None and max_price < min_price:
            raise serializers.ValidationError({
                "max_price": "Bei ya juu haiwezi kuwa chini ya bei ya chini."
            })
        return attrs