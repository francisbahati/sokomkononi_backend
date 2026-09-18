from rest_framework import serializers

from .models import Conversation, Message


class MessageUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class MessageSerializer(serializers.ModelSerializer):
    sender = MessageUserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "text",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class ConversationListingSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True,
    )
    location = serializers.CharField(read_only=True)


class ConversationSerializer(serializers.ModelSerializer):
    listing = ConversationListingSerializer(read_only=True)
    buyer = MessageUserSerializer(read_only=True)
    seller = MessageUserSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "listing",
            "buyer",
            "seller",
            "last_message",
            "last_message_at",
            "unread_count",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(is_read=False).exclude(
            sender=request.user,
        ).count()


class ConversationListSerializer(serializers.ModelSerializer):
    listing = ConversationListingSerializer(read_only=True)
    other_party = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "listing",
            "other_party",
            "last_message",
            "last_message_at",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def get_other_party(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        other = obj.seller if request.user.id == obj.buyer_id else obj.buyer
        return {"id": other.id, "name": other.name}

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(is_read=False).exclude(
            sender=request.user,
        ).count()


class ConversationCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField()
    initial_message = serializers.CharField(
        required=False, allow_blank=True, max_length=2000,
    )


class MessageCreateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)

    def validate_text(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Ujumbe hauwezi kuwa tupu.")
        return value