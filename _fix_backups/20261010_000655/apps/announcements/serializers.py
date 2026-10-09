from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    typeId = serializers.CharField(source="type", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id", "type", "typeId",
            "title", "title_en",
            "message", "message_en",
            "scheduled_for", "sent",
            "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class AnnouncementCreateSerializer(serializers.Serializer):
    typeId = serializers.ChoiceField(
        choices=Announcement.Type.choices,
        default=Announcement.Type.FEE_CHANGE,
    )
    title = serializers.CharField(max_length=255)
    titleEn = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
    message = serializers.CharField()
    messageEn = serializers.CharField(required=False, allow_blank=True)
    scheduledFor = serializers.DateTimeField(required=False, allow_null=True)
    sent = serializers.BooleanField(required=False, default=True)