from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "priority",
            "is_read",
            "read_at",
            "related_object_type",
            "related_object_id",
            "action_url",
            "created_at",
        ]

        read_only_fields = fields


class NotificationMarkReadSerializer(serializers.Serializer):
    pass