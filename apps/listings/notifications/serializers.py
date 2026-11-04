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
        Stored `action_url` is authoritative — the frontend knows how
        to route it. Only fall back to the reverse-resolved API URL
        when the stored value is empty.
        """
        return obj.action_url or obj.resolved_action_url or None


class NotificationMarkReadSerializer(serializers.Serializer):
    pass

class NotificationCreateSerializer(serializers.Serializer):
    """
    Frontend-friendly create serializer.

    Rules:
      - recipient is ALWAYS the caller — you cannot create a
        notification for another user.
      - audience="admin" requires is_staff. Otherwise forced to "user".
      - related_object_id / related_object_type / action_url are optional.
      - Accepts both snake_case and camelCase field names.
    """
    notification_type = serializers.CharField(max_length=50, required=False, default="GENERAL")
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    priority = serializers.ChoiceField(
        choices=["LOW", "NORMAL", "HIGH", "URGENT"],
        required=False, default="NORMAL",
    )
    audience = serializers.ChoiceField(
        choices=["user", "admin"],
        required=False, default="user",
    )
    related_object_type = serializers.CharField(
        max_length=100, required=False, allow_blank=True,
    )
    related_object_id = serializers.IntegerField(
        required=False, allow_null=True,
    )
    action_url = serializers.CharField(
        max_length=500, required=False, allow_blank=True,
    )

    def to_internal_value(self, data):
        try:
            d = data.copy()
        except AttributeError:
            d = dict(data)
        # camelCase aliases the frontend may send
        for camel, snake in (
            ("notificationType", "notification_type"),
            ("relatedObjectType", "related_object_type"),
            ("relatedObjectId", "related_object_id"),
            ("actionUrl", "action_url"),
        ):
            if camel in d and snake not in d:
                d[snake] = d.pop(camel)
        # Accept whitespace-trimmed title/message
        for k in ("title", "message"):
            if k in d and isinstance(d[k], str):
                d[k] = d[k].strip()
        return super().to_internal_value(d)

    def validate_title(self, v):
        if not v:
            raise serializers.ValidationError("Kichwa kinahitajika.")
        return v

    def validate_message(self, v):
        if not v:
            raise serializers.ValidationError("Ujumbe unahitajika.")
        return v

    def validate_notification_type(self, v):
        # Accept any string — the model will validate against choices.
        return (v or "GENERAL").upper()

    def validate(self, attrs):
        # audience=admin requires staff
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if attrs.get("audience") == "admin" and not getattr(user, "is_staff", False):
            # Silently downgrade — no error, just make it a user notification.
            attrs["audience"] = "user"
        return attrs
