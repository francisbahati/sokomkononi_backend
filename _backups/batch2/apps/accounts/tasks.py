"""Celery tasks for accounts: async email + cleanup."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name="accounts.send_otp_email",
    bind=True,
    max_retries=5,
)
def send_otp_email_task(self, recipient, otp, purpose="register"):
    """Send OTP. `recipient` can be a user id or an email string."""
    from apps.accounts.models import User
    from apps.accounts.email_service import send_otp_email

    user = None
    if isinstance(recipient, int):
        try:
            user = User.all_objects.get(pk=recipient)
        except User.DoesNotExist:
            logger.warning("OTP task: user %s gone", recipient)
            return {"ok": False, "reason": "no_user"}
    else:
        user = recipient  # email string

    result = send_otp_email(user=user, otp=otp, purpose=purpose)
    if result.ok:
        return {"ok": True}

    countdown = min(30 * (2 ** self.request.retries), 600)
    logger.warning(
        "OTP send failed for %s (attempt %s) — retry in %ss",
        recipient, self.request.retries + 1, countdown,
    )
    raise self.retry(countdown=countdown, exc=Exception(result.error or "send_failed"))


@shared_task(name="accounts.send_welcome_email")
def send_welcome_email_task(user_id):
    from apps.accounts.models import User
    from apps.accounts.email_service import send_welcome_email

    try:
        user = User.all_objects.get(pk=user_id)
    except User.DoesNotExist:
        return {"ok": False, "reason": "no_user"}
    return {"ok": send_welcome_email(user=user).ok}


@shared_task(name="accounts.cleanup_old_otps")
def cleanup_old_otps():
    from apps.accounts.models import OTPVerification
    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = OTPVerification.objects.filter(created_at__lt=cutoff).delete()
    logger.info("cleanup_old_otps: deleted=%s", deleted)
    return {"deleted": deleted}


@shared_task(name="accounts.cleanup_expired_tokens")
def cleanup_expired_tokens():
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    except ImportError:
        return {"deleted": 0}
    deleted, _ = OutstandingToken.objects.filter(expires_at__lt=timezone.now()).delete()
    logger.info("cleanup_expired_tokens: deleted=%s", deleted)
    return {"deleted": deleted}
