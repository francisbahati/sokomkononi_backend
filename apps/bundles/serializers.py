from rest_framework import serializers

from .models import Bundle, BundlePurchase


class BundleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    validityDays = serializers.IntegerField(source="validity_days")
    discountPercent = serializers.IntegerField(source="discount_percent")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Canonical credits shape: {service_key: count}
        credits = data.get("credits")
        if isinstance(credits, list):
            normalised = {}
            for item in credits:
                if isinstance(item, dict):
                    key = item.get("service") or item.get("service_key") or item.get("key")
                    count = item.get("count") or item.get("amount") or 1
                    if key:
                        normalised[str(key)] = int(count)
            data["credits"] = normalised
        elif not isinstance(credits, dict):
            data["credits"] = {}
        return data

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
    bundle_name = serializers.CharField(source="bundle.name_sw", read_only=True)

    class Meta:
        model = BundlePurchase
        fields = [
            "id", "bundle", "bundle_code", "bundle_name",
            "amount", "credits", "credits_snapshot",
            "services", "services_snapshot",
            "status", "payment_reference", "payment_status",
            "paid_at", "expires_at", "created_at", "updated_at",
        ]
        read_only_fields = fields

    # `credits` mirrors `credits_snapshot` under the canonical name the
    # frontend reads.
    credits = serializers.JSONField(source="credits_snapshot", read_only=True)
    services = serializers.JSONField(source="services_snapshot", read_only=True)
    payment_status = serializers.CharField(source="status", read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class BundlePurchaseCreateSerializer(serializers.Serializer):
    bundle = serializers.PrimaryKeyRelatedField(
        queryset=Bundle.objects.filter(active=True),
    )
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
