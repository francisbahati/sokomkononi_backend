from rest_framework import serializers

from .models import ContactMessage


class ContactCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=30, required=False, allow_blank=True,
    )
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()

    def validate_message(self, value):
        value = (value or "").strip()
        if len(value) < 10:
            raise serializers.ValidationError(
                "Ujumbe lazima uwe na angalau herufi 10."
            )
        return value


class ContactReplySerializer(serializers.Serializer):
    reply_note = serializers.CharField(required=False, allow_blank=True)


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = [
            "id", "name", "email", "phone", "subject", "message",
            "status", "reply_note", "replied_at", "created_at",
        ]
        read_only_fields = fields
