from rest_framework import serializers

from .models import Bundle, BundlePurchase


# ============================================================================
# BUNDLE
# ============================================================================

class BundleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    # Camel-case fields for output (frontend inasoma camelCase).
    # Kwa input, tunatumia `to_internal_value` kubadilisha camelCase → snake_case.
    validityDays = serializers.IntegerField(
        source="validity_days",
        required=False,
    )
    discountPercent = serializers.IntegerField(
        source="discount_percent",
        required=False,
    )

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

    # ---------------------------------------------------------------
    # NORMALIZE INPUT
    # Kubali `validityDays` AU `validity_days` (na vivyo hivyo kwa
    # `discountPercent`/`discount_percent`).
    # ---------------------------------------------------------------
    def to_internal_value(self, data):
        try:
            normalized = data.copy()
        except AttributeError:
            normalized = dict(data)

        # Normalize validity days
        if "validityDays" in normalized and "validity_days" not in normalized:
            normalized["validity_days"] = normalized["validityDays"]
        normalized.pop("validityDays", None)

        # Normalize discount percent
        if "discountPercent" in normalized and "discount_percent" not in normalized:
            normalized["discount_percent"] = normalized["discountPercent"]
        normalized.pop("discountPercent", None)

        return super().to_internal_value(normalized)

    # ---------------------------------------------------------------
    # NORMALIZE OUTPUT
    # Canonical credits shape: {service_key: count}
    # ---------------------------------------------------------------
    def to_representation(self, instance):
        data = super().to_representation(instance)

        credits = data.get("credits")
        if isinstance(credits, list):
            normalized = {}
            for item in credits:
                if isinstance(item, dict):
                    key = (
                        item.get("service")
                        or item.get("service_key")
                        or item.get("key")
                    )
                    count = (
                        item.get("count")
                        or item.get("amount")
                        or 1
                    )
                    if key:
                        normalized[str(key)] = int(count)
            data["credits"] = normalized
        elif not isinstance(credits, dict):
            data["credits"] = {}

        return data

    def get_name(self, obj):
        return {"sw": obj.name_sw, "en": obj.name_en}

    def get_description(self, obj):
        return {"sw": obj.description_sw, "en": obj.description_en}


# ============================================================================
# BUNDLE PURCHASE
# ============================================================================

class BundlePurchaseSerializer(serializers.ModelSerializer):
    bundle_code = serializers.CharField(source="bundle.code", read_only=True)
    bundle_name = serializers.CharField(source="bundle.name_sw", read_only=True)

    # `credits` mirrors `credits_snapshot` under the canonical name the
    # frontend reads.
    credits = serializers.JSONField(source="credits_snapshot", read_only=True)
    services = serializers.JSONField(source="services_snapshot", read_only=True)
    payment_status = serializers.CharField(source="status", read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

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


# ============================================================================
# BUNDLE PURCHASE — CREATE
# ============================================================================

class BundlePurchaseCreateSerializer(serializers.Serializer):
    bundle = serializers.PrimaryKeyRelatedField(
        queryset=Bundle.objects.filter(active=True),
    )
    payment_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )