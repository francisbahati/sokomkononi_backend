from rest_framework import serializers


# ============================================================
# ADMIN DASHBOARD
# ============================================================

class FinancialDashboardSerializer(serializers.Serializer):
    period = serializers.CharField()

    start = serializers.DateTimeField(allow_null=True, read_only=True)
    end = serializers.DateTimeField(allow_null=True, read_only=True)

    total_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)
    listing_fee_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)
    reservation_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)
    boosting_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)
    advertisement_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)
    bundle_revenue = serializers.DecimalField(
        max_digits=20, decimal_places=2, required=False,
    )
    leading_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)

    refunds = serializers.DecimalField(max_digits=20, decimal_places=2)
    net_revenue = serializers.DecimalField(max_digits=20, decimal_places=2)

    paid_listing_fees = serializers.IntegerField()
    paid_reservations = serializers.IntegerField()
    paid_boosts = serializers.IntegerField()
    paid_banners = serializers.IntegerField(required=False)
    paid_bundles = serializers.IntegerField(required=False)
    refund_count = serializers.IntegerField()


# ============================================================
# ADMIN REVENUE REPORT
# ============================================================

class RevenueRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    source = serializers.CharField()
    source_label = serializers.CharField()

    amount = serializers.DecimalField(max_digits=20, decimal_places=2)

    payment_status = serializers.CharField()

    payment_reference = serializers.CharField(allow_null=True, allow_blank=True)
    paid_at = serializers.DateTimeField(allow_null=True)
    refunded_at = serializers.DateTimeField(allow_null=True)

    seller_id = serializers.IntegerField(allow_null=True)
    seller_name = serializers.CharField(allow_null=True, allow_blank=True)
    seller_email = serializers.EmailField(allow_null=True, allow_blank=True)

    listing_id = serializers.IntegerField(allow_null=True)
    listing_title = serializers.CharField(allow_null=True, allow_blank=True)

    status = serializers.CharField(allow_null=True, allow_blank=True)
    created_at = serializers.DateTimeField()


# ============================================================
# USER-SIDE MY TRANSACTIONS
# ============================================================

class MyTransactionSerializer(serializers.Serializer):
    id = serializers.CharField()
    source = serializers.CharField()
    ref = serializers.CharField()
    type = serializers.CharField()
    title = serializers.CharField()

    listing_id = serializers.IntegerField(allow_null=True)
    listing_title = serializers.CharField(allow_null=True, allow_blank=True)

    amount = serializers.DecimalField(max_digits=20, decimal_places=2)

    status = serializers.CharField()
    payment_status = serializers.CharField()
    payment_reference = serializers.CharField(allow_null=True, allow_blank=True)
    method = serializers.CharField(allow_null=True, allow_blank=True)

    paid_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
