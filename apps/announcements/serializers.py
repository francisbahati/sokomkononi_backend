# ============================================================
# apps/announcements/serializers.py
#
# Marekebisho:
#  - AnnouncementCreateSerializer.sent: ondoa default=True
#    ili views.create() iweze kuamua sent = not scheduled_for
#    (bila hii, scheduled_for iliyowekwa ilikuwa inatumwa mara moja)
#  - AnnouncementSerializer: typeId ni read-only mirror ya type
#  - `is_published` + `status` (SENT | SCHEDULED | DRAFT) zinahesabiwa
#    na server: tangazo lenye scheduled_for linahesabiwa limetumwa pale
#    muda unapofika, bila kutegemea cron/Celery kugeuza `sent`
#  - AnnouncementUpdateSerializer (PATCH ya matangazo yaliyopangwa)
# ============================================================
from rest_framework import serializers

from .models import Announcement
from .services import is_published


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
    is_published = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    @staticmethod
    def published(obj, now=None):
        """Kanuni moja ya 'imetumwa' — iko kwenye services.is_published."""
        return is_published(obj, now)

    def get_is_published(self, obj):
        return self.published(obj)

    def get_status(self, obj):
        if self.published(obj):
            return "SENT"
        return "SCHEDULED" if obj.scheduled_for else "DRAFT"

    class Meta:
        model = Announcement
        fields = [
            "id", "type", "typeId",
            "title", "title_en",
            "message", "message_en",
            "scheduled_for", "sent",
            "is_published", "status", "dispatched_at",
            "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "dispatched_at"]


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
    # Inapokelewa kwa backwards-compat lakini INAPUUZWA: server huamua
    # `sent` kutokana na scheduled_for (angalia views.create).
    sent = serializers.BooleanField(required=False)


class AnnouncementUpdateSerializer(serializers.Serializer):
    """PATCH — matangazo ambayo bado hayajatumwa tu. Fields zote ni hiari."""

    type = serializers.ChoiceField(choices=Announcement.Type.choices, required=False)
    title = serializers.CharField(max_length=255, required=False)
    title_en = serializers.CharField(max_length=255, required=False, allow_blank=True)
    message = serializers.CharField(required=False)
    message_en = serializers.CharField(required=False, allow_blank=True)
    # allow_null=False: kuondoa ratiba = tumia /send-now/ (au futa tangazo)
    scheduled_for = serializers.DateTimeField(required=False)