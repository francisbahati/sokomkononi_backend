from django.db import transaction
from django.utils import timezone

from ..models import Notification


@transaction.atomic
def create_notification(
    *,
    recipient,
    notification_type,
    title,
    message,
    priority=Notification.Priority.NORMAL,
    related_object_type="",
    related_object_id=None,
    action_url="",
):
    """
    Create a notification for a user.
    """

    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        action_url=action_url,
    )


@transaction.atomic
def mark_notification_as_read(*, notification, user):
    """
    Mark one notification as read.
    """

    if notification.recipient_id != user.id and not user.is_staff:
        raise PermissionError(
            "Huruhusiwi kubadilisha arifa ya mtumiaji mwingine."
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=[
                "is_read",
                "read_at",
                "updated_at",
            ]
        )

    return notification


@transaction.atomic
def mark_all_notifications_as_read(*, user):
    """
    Mark all unread notifications belonging to the user as read.
    """

    now = timezone.now()

    return (
        Notification.objects
        .filter(
            recipient=user,
            is_read=False,
        )
        .update(
            is_read=True,
            read_at=now,
            updated_at=now,
        )
    )


def get_unread_notification_count(*, user):
    """
    Return the number of unread notifications for a user.
    """

    return Notification.objects.filter(
        recipient=user,
        is_read=False,
    ).count()