# ============================================================
# apps/announcements/views.py
#
# AnnouncementViewSet — Admin CRUD + public reads.
#
# Marekebisho:
#  - Ondoa __import__() — tumia timezone + Q moja kwa moja
#  - create(): sent default = False kama scheduled_for ipo
#  - Audit logging kupitia _log() helper
# ============================================================
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAdminUser  # noqa: E402
from .models import Announcement
from .serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
)


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details=""):
    """Helper — ina-logi admin action bila kuvunja request kama log inashindwa."""
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
        )


class AnnouncementViewSet(viewsets.GenericViewSet):
    """
        GET     /api/announcements/          public: sent ones; admin: all
        GET     /api/announcements/sent/     public: sent ones (paginated)
        GET     /api/announcements/{id}/     public: detail
        POST    /api/announcements/          admin only
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

        # Admin/staff wanaona zote
        if user.is_authenticated and user.is_staff:
            return qs

        # Public: sent ones tu, na scheduled_for haijapita au haipo
        now = timezone.now()
        return qs.filter(sent=True).filter(
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now)
        )

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
        qs = Announcement.objects.filter(sent=True).filter(
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now)
        )
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

        # sent default: False kama scheduled_for ipo, True kama haipo
        scheduled = d.get("scheduled_for")
        sent = d.get("sent")
        if sent is None:
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

        _log(
            request,
            action="announcement.created",
            target="Announcement",
            target_id=obj.id,
            details=(
                f"Announcement: {obj.title} "
                f"(type={obj.type}, sent={obj.sent})"
            ),
        )

        return Response(
            AnnouncementSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------
    # DESTROY — admin only
    # ------------------------------------------------------------
    def destroy(self, request, pk=None):
        obj = self.get_object()

        obj_id = obj.id
        obj_title = obj.title

        obj.delete()

        _log(
            request,
            action="announcement.deleted",
            target="Announcement",
            target_id=obj_id,
            details=f"Deleted announcement: {obj_title}",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)