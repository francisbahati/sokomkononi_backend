"""Messaging notifications."""
from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification


def notify_new_message(*, conversation, message):
    recipient = (
        conversation.seller
        if message.sender_id == conversation.buyer_id
        else conversation.buyer
    )
    preview = (message.text or "")[:120]
    create_notification(
        recipient=recipient,
        notification_type=Notification.NotificationType.GENERAL,
        title="Ujumbe Mpya",
        message=f"{message.sender.name}: {preview}",
        priority=Notification.Priority.NORMAL,
        related_object_type="Conversation",
        related_object_id=conversation.id,
        action_url=f"/messages/{conversation.id}",
    )
