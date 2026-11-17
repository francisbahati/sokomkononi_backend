# ============================================================
# apps/announcements/views.py
#
# AnnouncementViewSet — Admin CRUD + public reads.
#
# Marekebisho:
#  - Ondoa __import__() — tumia timezone + Q moja kwa moja
#  - create(): sent default = False kama scheduled_for ipo
#  - Audit logging kupitia _log() helper (sasa na params=)
#  - Scheduling: tangazo lenye scheduled_for linaonekana kwa umma pale
#    muda unapofika (bila cron). Flag `sent` inasawazishwa kwa staff.
#  - create(): scheduled_for lazima iwe wakati ujao; `sent` ya mteja
#    inapuuzwa (server inaamua)
#  - POST /{id}/send-now/ — tuma tangazo lililopangwa sasa hivi
#  - PATCH /{id}/ — hariri/badilisha ratiba (ambazo hazijatumwa tu)
#  - Tangazo likitumwa (sasa/send-now/ratiba) watumiaji wote wanapata
#    arifa kupitia Celery (tasks.broadcast_announcement; flush_scheduled
#    iliyopo kwenye beat ni sweeper). Kufuta tangazo kunaondoa pia
#    arifa zake za bell.
#  - Flag `sent` inasawazishwa na tasks.flush_scheduled (si kwenye GET).
# ============================================================
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAdminUser  # noqa: E402
from .models import Announcement
from .serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    AnnouncementUpdateSerializer,
)
from .services import RELATED_TYPE, published_q

logger = logging.getLogger(__name__)


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details="", params=None):
    """Helper — ina-logi admin action bila kuvunja request kama log inashindwa."""
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
            params=params,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
        )


def _enqueue_broadcast(announcement_id):
    """
    Tuma arifa kwa watumiaji baada ya transaction kukamilika. Kama Celery
    haipatikani, flush_scheduled (beat) italichukua.
    """
    def _go():
        try:
            from .tasks import broadcast_announcement
            broadcast_announcement.delay(announcement_id)
        except Exception:
            logger.exception(
                "Could not enqueue announcement broadcast id=%s "
                "(flush_scheduled itajaribu tena)", announcement_id,
            )

    transaction.on_commit(_go)


class AnnouncementViewSet(viewsets.GenericViewSet):
    """
        GET     /api/announcements/          public: sent ones; admin: all
        GET     /api/announcements/sent/     public: sent ones (paginated)
        GET     /api/announcements/{id}/     public: detail
        POST    /api/announcements/          admin only
        PATCH   /api/announcements/{id}/     admin only (ambazo hazijatumwa)
        POST    /api/announcements/{id}/send-now/   admin only
        DELETE  /api/announcements/{id}/     admin only
    """

    serializer_class = AnnouncementSerializer

    # ------------------------------------------------------------
    # PERMISSIONS
    # ------------------------------------------------------------
    def get_permissions(self):
        if self.action in ["list", "retrieve", "sent"]:
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    # ------------------------------------------------------------
    # QUERYSET
    # ------------------------------------------------------------
    def get_queryset(self):
        user = self.request.user
        qs = Announcement.objects.all()
        now = timezone.now()

        # Admin/staff wanaona zote
        if user.is_authenticated and user.is_staff:
            return qs

        # Public: zilizotumwa tu (muda wa ratiba umefika)
        return qs.filter(published_q(now))

    # ------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------
    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = AnnouncementSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ------------------------------------------------------------
    # RETRIEVE
    # ------------------------------------------------------------
    def retrieve(self, request, pk=None):
        obj = self.get_object()
        return Response(AnnouncementSerializer(obj).data)

    # ------------------------------------------------------------
    # SENT — public, sent ones pekee
    # ------------------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        url_path="sent",
        permission_classes=[permissions.AllowAny],
    )
    def sent(self, request):
        now = timezone.now()
        qs = Announcement.objects.filter(published_q(now))
        page = self.paginate_queryset(qs)
        serializer = AnnouncementSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # ------------------------------------------------------------
    # CREATE — admin only
    # ------------------------------------------------------------
    def create(self, request):
        serializer = AnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        # Server inaamua: ratiba ya wakati ujao → itapangwa (sent=False);
        # bila ratiba → inatumwa sasa. `sent` ya mteja inapuuzwa.
        scheduled = d.get("scheduled_for")
        if scheduled and scheduled <= timezone.now():
            return Response(
                {"detail": "Ratiba lazima iwe wakati ujao.",
                 "scheduled_for": ["Ratiba lazima iwe wakati ujao."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sent = not scheduled

        obj = Announcement.objects.create(
            type=d["type"],
            title=d["title"],
            title_en=d.get("title_en", ""),
            message=d["message"],
            message_en=d.get("message_en", ""),
            scheduled_for=scheduled,
            sent=sent,
            created_by=request.user,
        )

        # ✅ Tumia params
        _log(
            request,
            action="announcement.created",
            target="Announcement",
            target_id=obj.id,
            params={"name": obj.title},
        )

        if sent:
            _enqueue_broadcast(obj.id)

        return Response(
            AnnouncementSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------
    # PARTIAL UPDATE — admin only, ambazo hazijatumwa tu
    # ------------------------------------------------------------
    def partial_update(self, request, pk=None):
        obj = self.get_object()
        if AnnouncementSerializer.published(obj):
            return Response(
                {"detail": "Tangazo limeshatumwa; haliwezi kuhaririwa. Lifute na uunde jipya."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = AnnouncementUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        new_sched = d.get("scheduled_for")
        if new_sched and new_sched <= timezone.now():
            return Response(
                {"detail": "Ratiba lazima iwe wakati ujao.",
                 "scheduled_for": ["Ratiba lazima iwe wakati ujao."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_sched = obj.scheduled_for
        for field, value in d.items():
            setattr(obj, field, value)
        obj.save(update_fields=list(d.keys()) or None)

        _log(
            request,
            action="announcement.updated",
            target="Announcement",
            target_id=obj.id,
            details={
                "sw": f"Tangazo '{obj.title}' limehaririwa"
                      + (f" (ratiba mpya: {obj.scheduled_for:%Y-%m-%d %H:%M})"
                         if new_sched and new_sched != old_sched else ""),
                "en": f"Announcement '{obj.title}' updated"
                      + (f" (new schedule: {obj.scheduled_for:%Y-%m-%d %H:%M})"
                         if new_sched and new_sched != old_sched else ""),
            },
        )
        return Response(AnnouncementSerializer(obj).data)

    # ------------------------------------------------------------
    # SEND NOW — tuma tangazo lililopangwa sasa hivi
    # ------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="send-now")
    def send_now(self, request, pk=None):
        obj = self.get_object()
        if AnnouncementSerializer.published(obj):
            return Response(
                {"detail": "Tangazo limeshatumwa."},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        old_sched = obj.scheduled_for
        # scheduled_for sasa ni "muda wa kutumwa" halisi (hakuna sent_at field).
        obj.scheduled_for = now
        obj.sent = True
        obj.save(update_fields=["scheduled_for", "sent"])
        _enqueue_broadcast(obj.id)

        _log(
            request,
            action="announcement.sent_now",
            target="Announcement",
            target_id=obj.id,
            details={
                "sw": f"Tangazo '{obj.title}' limetumwa sasa (lilipangwa: "
                      f"{old_sched:%Y-%m-%d %H:%M})" if old_sched else
                      f"Tangazo '{obj.title}' limetumwa sasa",
                "en": f"Announcement '{obj.title}' sent now (was scheduled: "
                      f"{old_sched:%Y-%m-%d %H:%M})" if old_sched else
                      f"Announcement '{obj.title}' sent now",
            },
        )
        return Response(AnnouncementSerializer(obj).data)

    # ------------------------------------------------------------
    # DESTROY — admin only
    # ------------------------------------------------------------
    def destroy(self, request, pk=None):
        obj = self.get_object()

        obj_id = obj.id
        obj_title = obj.title

        # Ondoa arifa za tangazo hili kwenye bell za watumiaji
        try:
            from apps.notifications.models import Notification
            Notification.all_objects.filter(
                related_object_type=RELATED_TYPE, related_object_id=obj_id,
            ).hard_delete()
        except Exception:
            logger.exception("Failed to remove notifications for announcement %s", obj_id)

        obj.delete()

        # ✅ Tumia params
        _log(
            request,
            action="announcement.deleted",
            target="Announcement",
            target_id=obj_id,
            params={"name": obj_title},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)