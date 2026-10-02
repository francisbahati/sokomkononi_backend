# apps/listings/serializers_fee_rules.py
from rest_framework import serializers

from .models import ListingFeeRule


class ListingFeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingFeeRule
        fields = [
            "id",
            "name",
            "min_price",
            "max_price",
            "percentage",
            "fee_mode",       # ⬅️ MPYA
            "flat_fee",       # ⬅️ MPYA
            "is_active",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]