# ============================================================
# apps/announcements/serializers.py
#
# Marekebisho:
#  - AnnouncementCreateSerializer.sent: ondoa default=True
#    ili views.create() iweze kuamua sent = not scheduled_for
#    (bila hii, scheduled_for iliyowekwa ilikuwa inatumwa mara moja)
#  - AnnouncementSerializer: typeId ni read-only mirror ya type
# ============================================================
from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    """
    Output serializer — inatumika kwa list, retrieve, sent, na
    response ya create/destroy.

    Inarudisha:
      - `type` (api value, mfano "FEE_CHANGE")
      - `typeId` (read-only mirror — same as type, kwa backwards-compat)
      - `title` / `title_en`
      - `message` / `message_en`
      - `scheduled_for` / `sent`
      - `created_by` / `created_at`
    """

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
    """
    Input serializer — inatumika kwenye POST /api/announcements/.

    Muhimu: `sent` haina default ili views.create() iweze
    kuamua:
      - Kama scheduled_for ipo  → sent = False (itapangwa)
      - Kama scheduled_for haipo → sent = True (itatumwa sasa)
    """

    type = serializers.ChoiceField(
        choices=Announcement.Type.choices,
        default=Announcement.Type.FEE_CHANGE,
    )
    title = serializers.CharField(max_length=255)
    title_en = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
    message = serializers.CharField()
    message_en = serializers.CharField(required=False, allow_blank=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    sent = serializers.BooleanField(required=False)  # ⬅️ Ondoa default=True