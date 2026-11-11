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

# ============================================================
# CLEANUP — data-export faili za zamani
# ============================================================
@shared_task(name="accounts.cleanup_old_data_exports")
def cleanup_old_data_exports():
    """
    Futa faili za data-export zilizo na zaidi ya DATA_EXPORT_RETENTION_DAYS.

    Inarun kila siku saa 3:30 asubuhi.

    Inatumia `default_storage` — kwa local (FileSystemStorage) au R2
    (CloudflareR2MediaStorage). Kwa R2, tunatumia listdir + delete.
    """
    from django.conf import settings
    from django.core.files.storage import default_storage

    retention_days = getattr(settings, "DATA_EXPORT_RETENTION_DAYS", 7)
    cutoff = timezone.now() - timedelta(days=retention_days)

    deleted = 0
    scanned = 0
    errors = 0

    try:
        # Angalia kama storage inaunga mkono `listdir`
        if not hasattr(default_storage, "listdir"):
            logger.warning(
                "cleanup_old_data_exports: storage haina listdir — skip."
            )
            return {"deleted": 0, "reason": "storage_no_listdir"}

        # Orodhesha `data-exports/` — kila user ana folder yake
        try:
            top_dirs, _files = default_storage.listdir("data-exports")
        except FileNotFoundError:
            return {"deleted": 0, "scanned": 0, "reason": "no_exports_dir"}
        except Exception:
            logger.exception("cleanup_old_data_exports: top-level listdir failed")
            return {"deleted": 0, "errors": 1}

        for user_dir in top_dirs:
            user_path = f"data-exports/{user_dir}"

            try:
                _subdirs, files = default_storage.listdir(user_path)
            except Exception:
                errors += 1
                continue

            for fname in files:
                scanned += 1
                fpath = f"{user_path}/{fname}"
                try:
                    # Pata mtime kwa njia tofauti kulingana na storage
                    mtime = None

                    # Jaribu `get_modified_time` (django-storages S3/R2)
                    try:
                        mtime = default_storage.get_modified_time(fpath)
                        if mtime and timezone.is_naive(mtime):
                            mtime = timezone.make_aware(mtime)
                    except (AttributeError, NotImplementedError):
                        mtime = None

                    # Fallback kwa local storage
                    if mtime is None:
                        try:
                            import os
                            from pathlib import Path
                            local_path = Path(default_storage.path(fpath))
                            if local_path.exists():
                                mtime = timezone.datetime.fromtimestamp(
                                    local_path.stat().st_mtime,
                                    tz=timezone.utc,
                                )
                        except (AttributeError, NotImplementedError, FileNotFoundError):
                            mtime = None

                    if mtime is None:
                        # Hatujui muda — ruka (usi-risk kufuta makosa)
                        continue

                    if mtime < cutoff:
                        default_storage.delete(fpath)
                        deleted += 1
                except Exception:
                    errors += 1
                    logger.exception(
                        "cleanup_old_data_exports: failed file=%s", fpath
                    )

        logger.info(
            "cleanup_old_data_exports: scanned=%s deleted=%s errors=%s",
            scanned, deleted, errors,
        )
        return {"scanned": scanned, "deleted": deleted, "errors": errors}

    except Exception:
        logger.exception("cleanup_old_data_exports: unexpected failure")
        return {"deleted": 0, "errors": 1}