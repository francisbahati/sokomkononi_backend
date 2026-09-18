from django.utils import timezone

from ..models import Notification


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
    Create a notification. Callers that run inside an atomic block
    should invoke this via transaction.on_commit() to avoid coupling
    the notification write to the business transaction.
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


def mark_notification_as_read(*, notification, user):
    if notification.recipient_id != user.id and not user.is_staff:
        raise PermissionError(
            "Huruhusiwi kubadilisha arifa ya mtumiaji mwingine."
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(
            update_fields=["is_read", "read_at", "updated_at"],
        )

    return notification


def mark_all_notifications_as_read(*, user):
    now = timezone.now()
    return (
        Notification.objects
        .filter(recipient=user, is_read=False)
        .update(is_read=True, read_at=now, updated_at=now)
    )


def get_unread_notification_count(*, user):
    return Notification.objects.filter(
        recipient=user, is_read=False,
    ).count()