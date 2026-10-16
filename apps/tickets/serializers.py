from rest_framework import serializers
from django.db import models   

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
    deal_room_id = serializers.IntegerField(source="deal_room.id", read_only=True)
    reported_user_id = serializers.IntegerField(source="reported_user.id", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "code", "subject", "description",
            "user", "user_name", "user_email",
            "category", "priority", "status",
            "assigned_to", "assigned_to_name",
            "resolved_at", "sla_deadline", "sla_reminded_at",
            "sla_overdue",
            # ── Deal Report context ──
            "deal_room_id", "reported_user_id", "reported_user_name",
            "reporter_role", "report_reason",
            "messages", "attachments",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "code", "user", "user_name", "user_email",
            "assigned_to", "assigned_to_name", "resolved_at",
            "sla_deadline", "sla_reminded_at", "sla_overdue",
            "deal_room_id", "reported_user_id", "reported_user_name",
            "reporter_role", "report_reason",
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


# ============================================================
# DEAL REPORT — inatumika kwenye apps.deals.views
# ============================================================
class DealReportReason(models.TextChoices):
    FRAUD = "FRAUD", "Utapeli / Uongo"
    HARASSMENT = "HARASSMENT", "Unyanyasaji / Vitisho"
    NO_SHOW = "NO_SHOW", "Hakufika kwenye Ukaguzi"
    FAKE_DOCS = "FAKE_DOCS", "Hati za Uongo"
    OFF_PLATFORM = "OFF_PLATFORM", "Kutaka Malipo Nje ya Jukwaa"
    OTHER = "OTHER", "Nyingine"


class DealReportSerializer(serializers.Serializer):
    """
    Inatumika kwenye DealRoomViewSet.report — inaunda Ticket ya
    category=DEAL_REPORT.
    """
    reported_user_id = serializers.IntegerField(required=True)
    reason = serializers.ChoiceField(choices=DealReportReason.choices)
    details = serializers.CharField(
        required=True, min_length=10, max_length=4000,
        trim_whitespace=True,
    )

    def validate_details(self, value):
        value = (value or "").strip()
        if len(value) < 10:
            raise serializers.ValidationError(
                "Tafadhali toa maelezo ya kutosha (angalau herufi 10)."
            )
        return value

    def validate(self, attrs):
        deal_room = self.context.get("deal_room")
        request = self.context.get("request")

        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Ni lazima uwe umeingia kwenye akaunti."
            )
        if request.user.id not in [deal_room.buyer_id, deal_room.seller_id]:
            raise serializers.ValidationError(
                "Huruhusiwi kuripoti kwenye Deal Room hii."
            )

        reported_id = attrs.get("reported_user_id")
        if reported_id == request.user.id:
            raise serializers.ValidationError({
                "reported_user_id": "Huwezi kujiripoti mwenyewe."
            })
        if reported_id not in [deal_room.buyer_id, deal_room.seller_id]:
            raise serializers.ValidationError({
                "reported_user_id": (
                    "Mtumiaji huyo hayupo kwenye Deal Room hii."
                ),
            })

        # Zuia ripoti ya pili kwenye deal moja kwa mtumiaji huyo huyo
        existing = Ticket.objects.filter(
            category=Ticket.Category.DEAL_REPORT,
            deal_room=deal_room,
            user=request.user,
            reported_user_id=reported_id,
        ).exists()
        if existing:
            raise serializers.ValidationError(
                "Tayari umesharipoti mtumiaji huyu kwenye Deal Room hii. "
                "Timu yetu inachunguza."
            )

        return attrs