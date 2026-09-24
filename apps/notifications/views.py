from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import Notification
from .serializers import NotificationSerializer
from .services.notification import (
    get_unread_notification_count,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)


class NotificationViewSet(
    SoftDeleteViewSetMixin,
    viewsets.GenericViewSet,
):
    """
    API ya arifa za mtumiaji.

    Supports:
        list / retrieve
        POST   <pk>/read/           mark one as read
        POST   read-all/            mark all as read
        GET    unread-count/        count unread
        GET    unread/              list unread
        GET    priority/<X>/        filter by priority
        DELETE <pk>/                soft delete
        POST   <pk>/restore/        restore from trash
        GET    trash/               staff only
    """

    serializer_class = NotificationSerializer

    permission_classes = [
        permissions.IsAuthenticated,
    ]

    http_method_names = [
        "get",
        "post",
        "delete",
        "head",
        "options",
    ]

    owner_field = "recipient"

    queryset = (
        Notification.objects
        .select_related("recipient")
    )

    def get_queryset(self):
        user = self.request.user

        # Notifications are private. Even staff only see their own here.
        # Admins needing global views must use Django admin or a dedicated
        # audit endpoint.
        return self.queryset.filter(recipient=user)

    def list(self, request, *args, **kwargs):
        notifications = self.get_queryset()

        page = self.paginate_queryset(notifications)

        if page is not None:
            serializer = NotificationSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(serializer.data)

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

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()

        notification.delete(
            by=request.user,
            reason="",
        )

        return Response(
            {
                "detail": (
                    "Arifa imewekwa kwenye kikapu. "
                    "Itaondolewa kabisa baada ya siku 90."
                )
            },
            status=status.HTTP_200_OK,
        )

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
        url_path="trash",
    )
    def trash(self, request):
        # Only the owner's deleted notifications, unless the caller is
        # an admin who explicitly wants the global view (?scope=all).
        if request.user.is_staff and request.query_params.get("scope") == "all":
            qs = Notification.all_objects.filter(is_deleted=True)
        else:
            qs = Notification.all_objects.filter(
                recipient=request.user, is_deleted=True,
            )
        page = self.paginate_queryset(qs)
        serializer = NotificationSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

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

        page = self.paginate_queryset(notifications)

        if page is not None:
            serializer = NotificationSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(serializer.data)

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

        page = self.paginate_queryset(notifications)

        if page is not None:
            serializer = NotificationSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(serializer.data)

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(serializer.data)