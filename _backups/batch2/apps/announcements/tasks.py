# ============================================================
# apps/announcements/tasks.py
#
# Celery tasks for scheduled announcements.
#
# Marekebisho:
#  - flush_scheduled() sasa inatuma notifications kwa kila
#    announcement inayotumwa (push/SMS/email kupitia
#    apps.notifications.services.send_announcement)
#  - Inarudisha idadi ya announcements zilizotumwa
#  - Ina-log kila kosa la notification bila kuvunja task
# ============================================================
import logging

from celery import shared_task
from django.utils import timezone

from .models import Announcement

logger = logging.getLogger(__name__)


@shared_task(name="announcements.flush_scheduled")
def flush_scheduled():
    """
    Flip `sent=True` kwa announcements zilizopangwa (scheduled_for <= now),
    na tuma notifications kwa kila moja.

    Inaitwa na Celery Beat kila dakika (angalia settings.CELERY_BEAT_SCHEDULE).
    """
    now = timezone.now()

    pending = Announcement.objects.filter(
        sent=False,
        scheduled_for__isnull=False,
        scheduled_for__lte=now,
    ).order_by("scheduled_for")

    count = 0
    failed = 0

    for ann in pending:
        # 1. Flip sent=True kwanza ili tusitume mara mbili
        ann.sent = True
        ann.save(update_fields=["sent"])
        count += 1

        # 2. Tuma notification
        try:
            from apps.notifications.services import send_announcement
            send_announcement(ann)
        except Exception:
            failed += 1
            logger.exception(
                "announcements.flush_scheduled: notification failed for #%s",
                ann.id,
            )

    logger.info(
        "announcements.flush_scheduled: %s sent, %s notification failures",
        count, failed,
    )
    return {"sent": count, "failed": failed}