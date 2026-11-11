# apps/push/send.py
"""
Tuma push notification kwa mtumiaji kupitia pywebpush.

Inatumika na `apps/notifications/services/notification.py` kwenye
`_send_via_channel("push")`.
"""
import json
import logging

from django.conf import settings
from django.utils import timezone

from .models import PushSubscription

logger = logging.getLogger(__name__)


def send_push_to_user(
    *,
    user,
    title,
    body,
    url="/dashboard/notifications",
    tag=None,
    icon="/logo.webp",
):
    """
    Tuma push notification kwa subscriptions zote za mtumiaji.

    Inarudisha dict: { "sent": N, "failed": M, "deleted": K }

    - Subscriptions zenye 410 (Gone) au 404 zinafutwa (kifaa kimeondolewa).
    - Subscriptions zenye makosa mengine zinaachwa (jaribu tena baadaye).
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning(
            "[push] pywebpush haipo. Ongeza `pywebpush` kwenye requirements.txt."
        )
        return {"sent": 0, "failed": 0, "deleted": 0, "error": "pywebpush missing"}

    vapid_private = getattr(settings, "VAPID_PRIVATE_KEY", "")
    vapid_email = getattr(settings, "VAPID_ADMIN_EMAIL", "")
    if not vapid_private or not vapid_email:
        logger.warning(
            "[push] VAPID_PRIVATE_KEY au VAPID_ADMIN_EMAIL haipo kwenye settings."
        )
        return {"sent": 0, "failed": 0, "deleted": 0, "error": "VAPID not configured"}

    subs = PushSubscription.objects.filter(user=user)
    if not subs.exists():
        return {"sent": 0, "failed": 0, "deleted": 0}

    payload = json.dumps({
        "title": title or "SokoMkononi",
        "body": body or "",
        "url": url or "/dashboard/notifications",
        "tag": tag or None,
        "icon": icon,
    })

    sent = failed = deleted = 0

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": f"mailto:{vapid_email}"},
            )
            sent += 1
            PushSubscription.objects.filter(pk=sub.pk).update(
                last_used_at=timezone.now()
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None) if exc.response else None
            if status_code in (404, 410):
                # Kifaa kimeondolewa au kimeisha — futa subscription
                sub.delete()
                deleted += 1
            else:
                failed += 1
                logger.warning(
                    "[push] send failed for sub %s (%s): %s",
                    sub.pk, status_code, exc,
                )
        except Exception:
            failed += 1
            logger.exception("[push] unexpected error for sub %s", sub.pk)

    return {"sent": sent, "failed": failed, "deleted": deleted}