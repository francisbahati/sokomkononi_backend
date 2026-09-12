from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer
from .services.notification import (
    get_unread_notification_count,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)


class NotificationViewSet(viewsets.GenericViewSet):
    """
    API ya arifa za mtumiaji.
    """

    serializer_class = NotificationSerializer

    permission_classes = [
        permissions.IsAuthenticated,
    ]

    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    queryset = (
        Notification.objects
        .select_related("recipient")
    )

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return self.queryset

        return self.queryset.filter(
            recipient=user,
        )

    def list(self, request, *args, **kwargs):
        notifications = self.get_queryset()

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        notification = self.get_object()

        serializer = NotificationSerializer(
            notification,
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="read",
    )
    def mark_read(self, request, pk=None):
        notification = self.get_object()

        mark_notification_as_read(
            notification=notification,
            user=request.user,
        )

        serializer = NotificationSerializer(
            notification,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="read-all",
    )
    def mark_all_read(self, request):
        updated_count = mark_all_notifications_as_read(
            user=request.user,
        )

        return Response(
            {
                "detail": "Arifa zote zimesomwa.",
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="unread-count",
    )
    def unread_count(self, request):
        count = get_unread_notification_count(
            user=request.user,
        )

        return Response(
            {
                "unread_count": count,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="unread",
    )
    def unread(self, request):
        notifications = (
            self.get_queryset()
            .filter(is_read=False)
            .order_by("-created_at")
        )

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="priority/(?P<priority>[^/.]+)",
    )
    def by_priority(self, request, priority=None):
        valid_priorities = {
            choice[0]
            for choice in Notification.Priority.choices
        }

        priority = priority.upper()

        if priority not in valid_priorities:
            return Response(
                {
                    "detail": "Kipaumbele cha arifa si sahihi."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        notifications = (
            self.get_queryset()
            .filter(priority=priority)
            .order_by("-created_at")
        )

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(serializer.data)