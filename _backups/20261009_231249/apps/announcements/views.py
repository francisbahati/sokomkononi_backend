from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


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
        GET     /api/announcements/sent/
        POST    /api/announcements/          admin only
        DELETE  /api/announcements/{id}/     admin only
    """

    serializer_class = AnnouncementSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "sent"]:
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        qs = Announcement.objects.all()
        if user.is_authenticated and user.is_staff:
            return qs
        return qs.filter(sent=True)

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = AnnouncementSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        return Response(AnnouncementSerializer(obj).data)

    @action(detail=False, methods=["get"], url_path="sent",
            permission_classes=[permissions.AllowAny])
    def sent(self, request):
        qs = Announcement.objects.filter(sent=True)
        serializer = AnnouncementSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = AnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        obj = Announcement.objects.create(
            type=d["typeId"],
            title=d["title"],
            title_en=d.get("titleEn", ""),
            message=d["message"],
            message_en=d.get("messageEn", ""),
            scheduled_for=d.get("scheduledFor"),
            sent=d.get("sent", True),
            created_by=request.user,
        )

        _log(
            request,
            action="announcement.sent",
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