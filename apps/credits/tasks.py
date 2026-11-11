"""
Celery tasks for user credits.

Zeroes out credits that have passed their expiry so the frontend
stops showing stale balances.

+ notify_expiring_credits: inatuma notification kwa mtumiaji siku 7
na siku 1 kabla ya credits kuisha.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _, override

from .models import UserCredit, UserService


logger = logging.getLogger(__name__)


# ============================================================
# EXPIRE — zeroes out credits
# ============================================================
@shared_task(name="credits.expire_stale_credits")
def expire_stale_credits():
    now = timezone.now()

    credits = UserCredit.objects.filter(
        expires_at__lt=now,
        remaining__gt=0,
    )
    updated = credits.update(remaining=0)

    logger.info("expire_stale_credits: zeroed %s credit rows", updated)
    return {"zeroed": updated}


@shared_task(name="credits.cleanup_stale_services")
def cleanup_stale_services():
    now = timezone.now()
    count, _ = UserService.objects.filter(expires_at__lt=now).delete()
    logger.info("cleanup_stale_services: deleted %s service rows", count)
    return {"deleted": count}


# ============================================================
# NOTIFY EXPIRING — siku 7 na siku 1 kabla ya credits kuisha
# ============================================================
EXPIRY_WARNING_DAYS = 7
EXPIRY_FINAL_DAYS = 1
CACHE_KEY_PREFIX = "credits_expiry_notified"


def _notify_credits_expiry(credit, days_left):
    """
    Tuma notification kwa mtumiaji kuhusu credit inayoisha.

    days_left: 7 au 1 (kwa wording tofauti)
    """
    from apps.notifications.models import Notification
    from apps.notifications.services.notification import create_notification
    from apps.transactions.services._lang import user_lang

    user = credit.user
    service = credit.service_key
    remaining = credit.remaining
    bundle_name = credit.last_bundle_name or service

    lang = user_lang(user)

    if days_left <= EXPIRY_FINAL_DAYS:
        title = _("Credits zinaisha KESHO!")
        message = _(
            'Credits zako {n} za "{bundle}" zinaisha kesho. '
            "Zitumie kabla hazijapotea."
        ).format(n=remaining, bundle=bundle_name)
        priority = Notification.Priority.URGENT
    else:
        title = _("Credits zinaisha hivi karibuni")
        message = _(
            'Credits zako {n} za "{bundle}" zinaisha baada ya siku {days}. '
            "Zitumie kabla hazijapotea."
        ).format(n=remaining, bundle=bundle_name, days=days_left)
        priority = Notification.Priority.HIGH

    with override(lang):
        # Override `_()` context — tumia translation halisi
        if days_left <= EXPIRY_FINAL_DAYS:
            title_text = _("Credits zinaisha KESHO!")
            message_text = _(
                'Credits zako {n} za "{bundle}" zinaisha kesho. '
                "Zitumie kabla hazijapotea."
            ).format(n=remaining, bundle=bundle_name)
        else:
            title_text = _("Credits zinaisha hivi karibuni")
            message_text = _(
                'Credits zako {n} za "{bundle}" zinaisha baada ya siku {days}. '
                "Zitumie kabla hazijapotea."
            ).format(n=remaining, bundle=bundle_name, days=days_left)

        create_notification(
            recipient=user,
            notification_type=Notification.NotificationType.GENERAL,
            title=title_text,
            message=message_text,
            priority=priority,
            related_object_type="UserCredit",
            related_object_id=credit.id,
            action_url="/dashboard/bundles",
            side="both",
        )


@shared_task(name="credits.notify_expiring_credits")
def notify_expiring_credits():
    """
    Tuma notification kwa credits zinazoisha:
      - Siku 7 kabla (warning)
      - Siku 1 kabla (final reminder)

    Tumia cache kuzuia notification mbili kwa siku moja kwa credit moja.
    """
    now = timezone.now()
    final_threshold = now + timedelta(days=EXPIRY_FINAL_DAYS)
    warning_threshold = now + timedelta(days=EXPIRY_WARNING_DAYS)

    # Chukua credits zote zinazoisha ndani ya siku 7
    credits = (
        UserCredit.objects
        .filter(
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=warning_threshold,
            remaining__gt=0,
        )
        .select_related("user")
    )

    notified_warning = 0
    notified_final = 0
    skipped = 0

    for credit in credits.iterator(chunk_size=200):
        # Hesabu siku zilizobaki
        days_left = (credit.expires_at - now).days

        # Chagua aina ya notification (warning au final)
        if days_left <= EXPIRY_FINAL_DAYS:
            bucket = "final"
            cache_key = (
                f"{CACHE_KEY_PREFIX}:{credit.id}:final:"
                f"{credit.expires_at.date().isoformat()}"
            )
        else:
            bucket = "warning"
            cache_key = (
                f"{CACHE_KEY_PREFIX}:{credit.id}:warning:"
                f"{credit.expires_at.date().isoformat()}"
            )

        # Cache: zuia notification mbili kwa credit moja
        if not cache.add(cache_key, 1, timeout=60 * 60 * 24 * 2):
            skipped += 1
            continue

        try:
            _notify_credits_expiry(credit, days_left)
            if bucket == "final":
                notified_final += 1
            else:
                notified_warning += 1
        except Exception:
            logger.exception(
                "notify_expiring_credits: failed credit=%s", credit.pk
            )
            # Futa cache ili jaribio lingine lifanyike kesho
            cache.delete(cache_key)

    logger.info(
        "notify_expiring_credits: warning=%s final=%s skipped=%s",
        notified_warning, notified_final, skipped,
    )
    return {
        "warning": notified_warning,
        "final": notified_final,
        "skipped": skipped,
    }