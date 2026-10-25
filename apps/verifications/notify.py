# apps/verifications/notify.py

import logging

from django.conf import settings
from django.db import transaction as db_transaction

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

logger = logging.getLogger(__name__)


# ============================================================
# URL HELPER — huzalisha URL KAMILI kwa email
# ============================================================
def _absolute_url(path):
    """
    Badilisha relative path kuwa URL kamili.
    "/dashboard/verification" -> "https://sokomkononi.co.tz/dashboard/verification"
    """
    if not path:
        path = "/dashboard/verification"
    if path.startswith(("http://", "https://")):
        return path
    base = getattr(settings, "SITE_URL", "https://sokomkononi.co.tz")
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _send_email_safe(fn, **kwargs):
    """Helper — ina-log exception bila kuvunja mchakato mkuu."""
    try:
        from apps.accounts import email_service
        result = fn(**kwargs)
        if not result.ok:
            logger.warning(
                "[verifications.notify] email failed: %s", result.error,
            )
        return result
    except Exception:
        logger.exception("[verifications.notify] email exception")
        return None


def notify_approved(r):
    """
    Tuma notification + email kwa mtumiaji baada ya verification ku-approve.
    """
    def _notif():
        try:
            create_notification(
                recipient=r.user,
                notification_type=Notification.NotificationType.ACCOUNT_VERIFIED,
                title="Uthibitisho wako umeidhinishwa",
                message=(
                    f"Ombi lako la {r.type} limeidhinishwa. "
                    f"Sasa unaweza kufanya biashara kwa uhuru."
                ),
                priority=Notification.Priority.HIGH,
                related_object_type="verification",
                related_object_id=r.id,
                action_url="/dashboard/verification",  # ← app (React Router) inatumia relative
            )
        except Exception:
            logger.exception("notify_approved (notification) %s", r.id)

    def _email():
        try:
            from apps.accounts.email_service import (
                send_verification_approved_email,
            )
            send_verification_approved_email(
                to_email=r.user.email or r.user_email,
                name=r.user.name or r.user_name or "mteja",
                verification_type=r.type,
                action_url=_absolute_url("/dashboard/verification"),  # ✅ URL kamili
            )
        except Exception:
            logger.exception("notify_approved (email) %s", r.id)

    db_transaction.on_commit(_notif)
    db_transaction.on_commit(_email)


def notify_rejected(r, reason=""):
    """
    Tuma notification + email kwa mtumiaji baada ya verification ku-reject.
    """
    def _notif():
        try:
            create_notification(
                recipient=r.user,
                notification_type=Notification.NotificationType.GENERAL,
                title="Uthibitisho umekataliwa",
                message=f"Ombi lako la {r.type} limekataliwa. Sababu: {reason}",
                priority=Notification.Priority.HIGH,
                related_object_type="verification",
                related_object_id=r.id,
                action_url="/dashboard/verification",
            )
        except Exception:
            logger.exception("notify_rejected (notification) %s", r.id)

    def _email():
        try:
            from apps.accounts.email_service import (
                send_verification_rejected_email,
            )
            send_verification_rejected_email(
                to_email=r.user.email or r.user_email,
                name=r.user.name or r.user_name or "mteja",
                verification_type=r.type,
                reason=reason,
                action_url=_absolute_url("/dashboard/verification"),  # ✅
            )
        except Exception:
            logger.exception("notify_rejected (email) %s", r.id)

    db_transaction.on_commit(_notif)
    db_transaction.on_commit(_email)


def notify_documents_requested(r, message=""):
    """
    Tuma notification + email kwa mtumiaji kuhusu documents zaidi.
    """
    def _notif():
        try:
            create_notification(
                recipient=r.user,
                notification_type=Notification.NotificationType.GENERAL,
                title="Nyaraka zaidi zinahitajika",
                message=message or "Tafadhali pakia nyaraka zaidi.",
                priority=Notification.Priority.HIGH,
                related_object_type="verification",
                related_object_id=r.id,
                action_url="/dashboard/verification",
            )
        except Exception:
            logger.exception("notify_documents_requested (notification) %s", r.id)

    def _email():
        try:
            from apps.accounts.email_service import (
                send_documents_requested_email,
            )
            send_documents_requested_email(
                to_email=r.user.email or r.user_email,
                name=r.user.name or r.user_name or "mteja",
                message=message,
                action_url=_absolute_url("/dashboard/verification"),  # ✅
            )
        except Exception:
            logger.exception("notify_documents_requested (email) %s", r.id)

    db_transaction.on_commit(_notif)
    db_transaction.on_commit(_email)