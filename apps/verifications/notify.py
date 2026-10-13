import logging
from django.db import transaction as db_transaction
from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

logger = logging.getLogger(__name__)

def notify_approved(r):
    def _s():
        try:
            create_notification(recipient=r.user,
                notification_type=Notification.NotificationType.ACCOUNT_VERIFIED,
                title="Uthibitisho wako umeidhinishwa",
                message=f"Ombi lako la {r.type} limeidhinishwa.",
                priority=Notification.Priority.HIGH,
                related_object_type="verification", related_object_id=r.id,
                action_url="/dashboard/verification")
        except Exception: logger.exception("notify_approved %s", r.id)
    db_transaction.on_commit(_s)

def notify_rejected(r, reason=""):
    def _s():
        try:
            create_notification(recipient=r.user,
                notification_type=Notification.NotificationType.GENERAL,
                title="Uthibitisho umekataliwa",
                message=f"Ombi lako la {r.type} limekataliwa. Sababu: {reason}",
                priority=Notification.Priority.HIGH,
                related_object_type="verification", related_object_id=r.id,
                action_url="/dashboard/verification")
        except Exception: logger.exception("notify_rejected %s", r.id)
    db_transaction.on_commit(_s)

def notify_documents_requested(r, message=""):
    def _s():
        try:
            create_notification(recipient=r.user,
                notification_type=Notification.NotificationType.GENERAL,
                title="Nyaraka zaidi zinahitajika",
                message=message or "Tafadhali pakia nyaraka zaidi.",
                priority=Notification.Priority.HIGH,
                related_object_type="verification", related_object_id=r.id,
                action_url="/dashboard/verification")
        except Exception: logger.exception("notify_doc_req %s", r.id)
    db_transaction.on_commit(_s)
