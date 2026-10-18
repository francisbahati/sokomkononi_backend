from decimal import Decimal

from rest_framework import serializers

from .models import Payout, Refund


class CreateOrderSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("1"),
    )
    buyer_phone = serializers.CharField(max_length=20)
    buyer_email = serializers.EmailField(required=False, allow_blank=True)
    buyer_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True,
    )
    payment_method = serializers.ChoiceField(
        choices=["mobile", "card", "bank"], default="mobile",
    )
    redirect_url = serializers.URLField(required=False, allow_blank=True)


class OrderStatusSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=64)


class PayoutCreateSerializer(serializers.Serializer):
    MIN = Decimal("1000")
    MAX = Decimal("100000000")
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2,
        min_value=MIN, max_value=MAX,
    )
    method = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=64)
    account_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True,
    )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Kiasi lazima kiwe kikubwa kuliko sifuri."
            )
        return value


class PayoutSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.name", read_only=True,
    )

    class Meta:
        model = Payout
        fields = [
            "id", "withdrawal_id",
            "amount", "fee", "net_amount",
            "method", "account_number", "account_name",
            "status", "fimi_status", "failure_reason",
            "created_by", "created_by_name",
            "last_synced_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


# ============================================================
# REFUND SERIALIZER
# ============================================================
class RefundSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    user_phone = serializers.CharField(read_only=True)
    user_email = serializers.EmailField(read_only=True)
    user_payment_method = serializers.CharField(read_only=True)
    processed_by_name = serializers.CharField(
        source="processed_by.name", read_only=True,
    )

    class Meta:
        model = Refund
        fields = [
            "id", "promotion_type", "promotion_id",
            "user", "user_name",
            "user_phone", "user_email", "user_payment_method",
            "amount_paid", "amount_refunded",
            "status", "method", "reason", "admin_note",
            "processed_by", "processed_by_name",
            "payment_reference", "refund_reference",
            "created_at", "processed_at", "completed_at",
        ]
        read_only_fields = [
            "id", "created_at", "processed_at", "completed_at",
            "user_name", "user_phone", "user_email",
            "user_payment_method", "processed_by_name",
        ]