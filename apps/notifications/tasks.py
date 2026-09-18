"""
Celery tasks for the notifications app.
"""

import logging

from celery import shared_task

from .services.notification import (
    create_notification as _create_notification,
)


logger = logging.getLogger(__name__)


@shared_task(name="notifications.create")
def create_notification_task(
    recipient_id,
    notification_type,
    title,
    message,
    priority="NORMAL",
    related_object_type="",
    related_object_id=None,
    action_url="",
):
    """
    Create a notification asynchronously.

    Returns the created notification pk, or None if the recipient
    no longer exists.
    """
    from apps.accounts.models import User

    try:
        recipient = User.objects.get(pk=recipient_id)
    except User.DoesNotExist:
        logger.warning(
            "Notification recipient %s does not exist", recipient_id
        )
        return None

    notification = _create_notification(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        action_url=action_url,
    )

    return notification.pk