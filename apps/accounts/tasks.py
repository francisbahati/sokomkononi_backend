"""Celery tasks for accounts: async email + SMS delivery."""
import logging

from celery import shared_task

from .services import (
    send_email_otp as _sync_send_email_otp,
    send_sms_otp as _sync_send_sms_otp,
    send_password_reset_email as _sync_send_pw_email,
    send_password_reset_sms as _sync_send_pw_sms,
)

logger = logging.getLogger(__name__)


@shared_task(name="accounts.send_email_otp", bind=True, max_retries=3)
def send_email_otp_task(self, email, otp):
    try:
        _sync_send_email_otp(email, otp)
    except Exception as exc:
        logger.exception("send_email_otp failed for %s", email)
        raise self.retry(exc=exc, countdown=5)


@shared_task(name="accounts.send_sms_otp", bind=True, max_retries=3)
def send_sms_otp_task(self, phone, otp):
    try:
        _sync_send_sms_otp(phone, otp)
    except Exception as exc:
        logger.exception("send_sms_otp failed for %s", phone)
        raise self.retry(exc=exc, countdown=5)


@shared_task(name="accounts.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email_task(self, email, otp):
    try:
        _sync_send_pw_email(email, otp)
    except Exception as exc:
        logger.exception("send_password_reset_email failed for %s", email)
        raise self.retry(exc=exc, countdown=5)


@shared_task(name="accounts.send_password_reset_sms", bind=True, max_retries=3)
def send_password_reset_sms_task(self, phone, otp):
    try:
        _sync_send_pw_sms(phone, otp)
    except Exception as exc:
        logger.exception("send_password_reset_sms failed for %s", phone)
        raise self.retry(exc=exc, countdown=5)
