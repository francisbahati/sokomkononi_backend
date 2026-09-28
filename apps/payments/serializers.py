from rest_framework import serializers


class CreateOrderSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    buyer_phone = serializers.CharField(max_length=20)
    buyer_email = serializers.EmailField(required=False, allow_blank=True)
    buyer_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=["mobile", "card", "bank"], default="mobile",
    )
    redirect_url = serializers.URLField(required=False, allow_blank=True)


class OrderStatusSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=64)
