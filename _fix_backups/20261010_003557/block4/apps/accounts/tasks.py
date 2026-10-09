"""Celery tasks for accounts: async email delivery + periodic cleanup."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .services import (
    send_email_otp as _sync_send_email_otp,
    send_password_reset_email as _sync_send_pw_email,
)

logger = logging.getLogger(__name__)


@shared_task(name="accounts.send_email_otp", bind=True, max_retries=5)
def send_email_otp_task(self, email, otp):
    try:
        _sync_send_email_otp(email, otp)
    except Exception as exc:
        logger.exception("send_email_otp failed for %s", email)
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 5, 300))


@shared_task(name="accounts.send_password_reset_email", bind=True, max_retries=5)
def send_password_reset_email_task(self, email, otp):
    try:
        _sync_send_pw_email(email, otp)
    except Exception as exc:
        logger.exception("send_password_reset_email failed for %s", email)
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 5, 300))


@shared_task(name="accounts.cleanup_old_otps")
def cleanup_old_otps():
    """Remove OTPs older than 24h regardless of state."""
    from .models import OTPVerification
    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = OTPVerification.objects.filter(created_at__lt=cutoff).delete()
    logger.info("cleanup_old_otps: deleted=%s", deleted)
    return {"deleted": deleted}


@shared_task(name="accounts.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Prune OutstandingToken rows past their expiry."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            OutstandingToken,
        )
    except ImportError:
        return {"deleted": 0}
    now = timezone.now()
    deleted, _ = OutstandingToken.objects.filter(expires_at__lt=now).delete()
    logger.info("cleanup_expired_tokens: deleted=%s", deleted)
    return {"deleted": deleted}
