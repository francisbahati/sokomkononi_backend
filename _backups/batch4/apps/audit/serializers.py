# apps/audit/serializers.py

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Full serializer — inarudisha fields zote ikiwemo
    ip_address, user_agent, request_path, request_method.
    """
    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "admin_user", "admin_name",
            "target", "target_id", "details",
            "ip_address", "user_agent", "request_path", "request_method",
            "created_at",
        ]
        read_only_fields = fields