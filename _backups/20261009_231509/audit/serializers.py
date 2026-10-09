from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "admin_user", "admin_name",
            "target", "target_id", "details", "created_at",
        ]
        read_only_fields = fields