import logging

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Feedback
from .serializers import (
    FeedbackCreateSerializer,
    FeedbackRespondSerializer,
    FeedbackSerializer,
)

logger = logging.getLogger(__name__)


class FeedbackViewSet(viewsets.GenericViewSet):
    """
    Feedback endpoints.

        GET    /api/feedback/                admin: all feedback
        POST   /api/feedback/                user: submit feedback
        GET    /api/feedback/mine/           user: my submissions
        POST   /api/feedback/{id}/respond/   admin: reply
        DELETE /api/feedback/{id}/           owner or admin
    """

    serializer_class = FeedbackSerializer

    def get_permissions(self):
        if self.action == "respond":
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Feedback.objects.select_related("user", "listing", "replied_by")
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def list(self, request):
        if not request.user.is_staff:
            # Non-staff fall back to their own feedback
            qs = self.get_queryset().filter(user=request.user)
        else:
            qs = self.get_queryset()

        type_filter = request.query_params.get("type")
        status_filter = request.query_params.get("status")
        if type_filter:
            qs = qs.filter(type=type_filter.lower())
        if status_filter:
            qs = qs.filter(status=status_filter.lower())

        page = self.paginate_queryset(qs)
        serializer = FeedbackSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request):
        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        feedback = Feedback.objects.create(
            user=request.user,
            user_name=getattr(request.user, "name", "") or "",
            user_email=getattr(request.user, "email", "") or "",
            author_side=d.get("author_side") or Feedback.AuthorSide.SELLER,
            type=d.get("type") or Feedback.Type.FEEDBACK,
            subject=d["subject"],
            message=d["message"],
            rating=d.get("rating"),
            listing_id=d.get("listing_id"),
        )

        # Notify all admins (uses existing notifications service)
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services.notification import (
                create_notification_for_admins,
            )
            create_notification_for_admins(
                notification_type=Notification.NotificationType.GENERAL,
                title="Maoni mapya kutoka kwa mtumiaji",
                message=(
                    f"{feedback.user_name or feedback.user_email}: "
                    f"{feedback.subject}"
                ),
                priority=Notification.Priority.NORMAL,
                related_object_type="feedback.Feedback",
                related_object_id=feedback.id,
                action_url="/dashboard/admin/support?view=feedback",
            )
        except Exception:
            logger.exception("Failed to notify admins about feedback %s", feedback.pk)

        return Response(
            FeedbackSerializer(feedback).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        qs = Feedback.objects.filter(user=request.user).order_by("-created_at")
        page = self.paginate_queryset(qs)
        serializer = FeedbackSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="respond",
            permission_classes=[permissions.IsAdminUser])
    def respond(self, request, pk=None):
        feedback = Feedback.objects.filter(pk=pk).first()
        if not feedback:
            return Response(
                {"detail": "Maoni hayapatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = FeedbackRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback.admin_reply = serializer.validated_data["admin_reply"]
        feedback.replied_by = request.user
        feedback.replied_at = timezone.now()
        feedback.status = Feedback.Status.ANSWERED
        feedback.save(update_fields=[
            "admin_reply", "replied_by", "replied_at", "status", "updated_at",
        ])

        # Notify the author
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services.notification import create_notification
            create_notification(
                recipient=feedback.user,
                notification_type=Notification.NotificationType.GENERAL,
                title="Maoni yako yamejibiwa",
                message=f"SokoMkononi: {feedback.admin_reply[:200]}",
                priority=Notification.Priority.NORMAL,
                related_object_type="feedback.Feedback",
                related_object_id=feedback.id,
                action_url="/dashboard/feedback",
            )
        except Exception:
            logger.exception("Failed to notify feedback author %s", feedback.pk)

        return Response(FeedbackSerializer(feedback).data)

    def destroy(self, request, pk=None):
        feedback = Feedback.objects.filter(pk=pk).first()
        if not feedback:
            return Response(
                {"detail": "Maoni hayapatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if feedback.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        feedback.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
