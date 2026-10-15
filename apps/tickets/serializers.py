from rest_framework import serializers

from .models import Ticket, TicketAttachment, TicketMessage


class TicketAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = [
            "id", "name", "url", "is_image",
            "uploaded_by", "uploaded_by_name", "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        try:
            url = obj.file.url
        except Exception:
            return None
        return request.build_absolute_uri(url) if request else url

    def get_is_image(self, obj):
        if not obj.file:
            return False
        name = (obj.name or obj.file.name or "").lower()
        return name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


class TicketMessageSerializer(serializers.ModelSerializer):
    attachments = TicketAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            "id", "sender", "sender_name", "text",
            "attachments", "created_at",
        ]
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    sla_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id", "code", "subject", "description",
            "user", "user_name", "user_email",
            "category", "priority", "status",
            "assigned_to", "assigned_to_name",
            "resolved_at", "sla_deadline", "sla_reminded_at",
            "sla_overdue",
            "messages", "attachments",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "code", "user", "user_name", "user_email",
            "assigned_to", "assigned_to_name", "resolved_at",
            "sla_deadline", "sla_reminded_at", "sla_overdue",
            "messages", "attachments", "created_at", "updated_at",
        ]

    def get_sla_overdue(self, obj):
        """True kama SLA imepita na ticket haijatatuliwa."""
        from django.utils import timezone
        if not obj.sla_deadline:
            return False
        if obj.status in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED):
            return False
        return timezone.now() > obj.sla_deadline


class TicketCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(
        choices=Ticket.Category.choices,
        default=Ticket.Category.OTHER,
    )
    priority = serializers.ChoiceField(
        choices=Ticket.Priority.choices,
        default=Ticket.Priority.MEDIUM,
    )

    def validate_subject(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Kichwa linahitajika.")
        return value


class TicketMessageCreateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=5000, required=False, allow_blank=True)

    def validate(self, attrs):
        text = (attrs.get("text") or "").strip()
        files = self.context.get("files") or []
        if not text and not files:
            raise serializers.ValidationError(
                "Ujumbe au faili linahitajika."
            )
        attrs["text"] = text
        return attrs


class TicketStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Ticket.Status.choices)


class TicketPrioritySerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=Ticket.Priority.choices)


class TicketAssignSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()