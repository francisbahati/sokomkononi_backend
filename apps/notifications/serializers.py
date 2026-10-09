from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    action_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "priority",
            "audience",
            "is_read",
            "read_at",
            "related_object_type",
            "related_object_id",
            "action_url",
            "created_at",
        ]

        read_only_fields = fields

    def get_action_url(self, obj):
        """
        Rudisha URL sahihi ya API (dynamic).

        Inatumia obj.resolved_action_url — ambayo inatengeneza URL
        kutoka related_object_type + related_object_id.

        Inarudisha None kama object haipo au URL haijasajiliwa.
        """
        return obj.resolved_action_url


class NotificationMarkReadSerializer(serializers.Serializer):
    pass