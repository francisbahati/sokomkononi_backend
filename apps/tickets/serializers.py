from rest_framework import serializers

from .models import Ticket, TicketMessage


class TicketMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketMessage
        fields = [
            "id", "sender", "sender_name", "text", "created_at",
        ]
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "code", "subject", "description",
            "user", "user_name", "user_email",
            "category", "priority", "status",
            "assigned_to", "assigned_to_name",
            "resolved_at", "messages",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "code", "user", "user_name", "user_email",
            "assigned_to", "assigned_to_name", "resolved_at",
            "messages", "created_at", "updated_at",
        ]


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
    text = serializers.CharField(max_length=5000)

    def validate_text(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Ujumbe hauwezi kuwa tupu.")
        return value


class TicketStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Ticket.Status.choices)


class TicketPrioritySerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=Ticket.Priority.choices)


class TicketAssignSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()