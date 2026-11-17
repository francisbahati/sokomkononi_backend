# apps/bundles/serializers_admin.py
from rest_framework import serializers

from .models import BundlePurchase
from .stats import credits_total, sum_credits


class AdminBundlePurchaseSerializer(serializers.ModelSerializer):
    """Historia ya manunuzi kwa admin: mnunuzi, bundle, malipo na credits zilizotolewa."""

    bundle = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    credits = serializers.SerializerMethodField()
    credits_total = serializers.SerializerMethodField()
    services = serializers.JSONField(source="services_snapshot", read_only=True)

    class Meta:
        model = BundlePurchase
        fields = [
            "id", "bundle", "user", "amount", "status", "payment_reference",
            "paid_at", "expires_at", "created_at",
            "credits", "credits_total", "services",
        ]
        read_only_fields = fields

    def get_bundle(self, obj):
        b = obj.bundle
        return {
            "id": b.id,
            "code": b.code,
            "type": b.type,
            "name": {"sw": b.name_sw, "en": b.name_en},
        }

    def get_user(self, obj):
        u = obj.user
        return {
            "id": u.id,
            "name": getattr(u, "name", "") or "",
            "email": getattr(u, "email", None) or getattr(u, "deleted_email", None) or "",
            "phone": getattr(u, "phone", "") or "",
        }

    def get_credits(self, obj):
        return sum_credits(obj.credits_snapshot)

    def get_credits_total(self, obj):
        return credits_total(obj.credits_snapshot)
