# apps/audit/serializers.py

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Full serializer — inarudisha fields zote ikiwemo
    details_sw, details_en, ip_address, user_agent,
    request_path, request_method.
    """
    # ✅ Field mpya kwa ajili ya UI ya lugha mbili
    details_bilingual = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "admin_user", "admin_name",
            "target", "target_id",
            "details", "details_sw", "details_en", "details_bilingual",
            "ip_address", "user_agent", "request_path", "request_method",
            "created_at",
        ]
        read_only_fields = fields

    def get_details_bilingual(self, obj):
        """Rudisha dict yenye sw na en kwa ajili ya frontend."""
        return {
            "sw": obj.details_sw or obj.details or "",
            "en": obj.details_en or obj.details or "",
        }