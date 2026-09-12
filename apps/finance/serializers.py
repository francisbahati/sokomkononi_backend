
from rest_framework import serializers


class FinancialDashboardSerializer(serializers.Serializer):
    period = serializers.CharField()

    start = serializers.DateTimeField(
        allow_null=True,
        read_only=True,
    )

    end = serializers.DateTimeField(
        allow_null=True,
        read_only=True,
    )

    total_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    listing_fee_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    reservation_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    boosting_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    advertisement_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    leading_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    refunds = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    net_revenue = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    paid_listing_fees = serializers.IntegerField()
    paid_reservations = serializers.IntegerField()
    paid_boosts = serializers.IntegerField()
    refund_count = serializers.IntegerField()


class RevenueRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    source = serializers.CharField()
    source_label = serializers.CharField()

    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    payment_status = serializers.CharField()

    payment_reference = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )

    paid_at = serializers.DateTimeField(
        allow_null=True,
    )

    refunded_at = serializers.DateTimeField(
        allow_null=True,
    )

    seller_id = serializers.IntegerField(
        allow_null=True,
    )

    seller_name = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )

    seller_email = serializers.EmailField(
        allow_null=True,
        allow_blank=True,
    )

    listing_id = serializers.IntegerField(
        allow_null=True,
    )

    listing_title = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )

    status = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )

    created_at = serializers.DateTimeField()
