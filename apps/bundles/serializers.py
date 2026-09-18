from rest_framework import serializers

from .models import Bundle, BundlePurchase


class BundleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    validityDays = serializers.IntegerField(source="validity_days")
    discountPercent = serializers.IntegerField(source="discount_percent")

    class Meta:
        model = Bundle
        fields = [
            "id", "code", "type",
            "name", "description",
            "price", "credits",
            "validityDays", "services", "discountPercent",
            "icon", "color", "active", "featured", "ordering",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_name(self, obj):
        return {"sw": obj.name_sw, "en": obj.name_en}

    def get_description(self, obj):
        return {"sw": obj.description_sw, "en": obj.description_en}


class BundlePurchaseSerializer(serializers.ModelSerializer):
    bundle_code = serializers.CharField(source="bundle.code", read_only=True)

    class Meta:
        model = BundlePurchase
        fields = [
            "id", "bundle", "bundle_code",
            "amount", "credits_snapshot", "services_snapshot",
            "status", "payment_reference",
            "paid_at", "expires_at", "created_at",
        ]
        read_only_fields = fields


class BundlePurchaseCreateSerializer(serializers.Serializer):
    bundle = serializers.PrimaryKeyRelatedField(
        queryset=Bundle.objects.filter(active=True),
    )
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
