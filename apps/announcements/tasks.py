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
#  - MPYA: utoaji wa arifa unapitia services.dispatch_announcement
#    (claim ya `dispatched_at`) ili tangazo lisitume mara mbili, na
#    flush_scheduled pia inachukua matangazo ya papo hapo ambayo
#    trigger yake ilishindwa. Jina la task na beat schedule HAVIBADILIKI.
#  - MPYA: broadcast_announcement — trigger ya papo hapo (create/send-now)
# ============================================================
import logging

from celery import shared_task
from django.utils import timezone

from .services import dispatch_announcement, dispatch_pending, sync_due

logger = logging.getLogger(__name__)


@shared_task(name="announcements.flush_scheduled")
def flush_scheduled():
    """
    1. Flip `sent=True` kwa announcements zilizopangwa (scheduled_for <= now).
    2. Tuma notifications kwa kila tangazo lililotumwa lakini bado
       halijafikishiwa watumiaji (claim ya dispatched_at inazuia nakala).

    Inaitwa na Celery Beat kila dakika (angalia settings.CELERY_BEAT_SCHEDULE).
    """
    now = timezone.now()

    flipped = sync_due(now)
    results = dispatch_pending(now)

    sent = sum(1 for r in results.values() if r.get("status") == "sent")
    failed = sum(1 for r in results.values() if r.get("status") == "error")

    logger.info(
        "announcements.flush_scheduled: %s flipped, %s notified, %s notification failures",
        flipped, sent, failed,
    )
    return {"flipped": flipped, "sent": sent, "failed": failed}


@shared_task(name="announcements.broadcast", bind=True, max_retries=3)
def broadcast_announcement(self, announcement_id):
    """
    Trigger ya papo hapo (tangazo bila ratiba, au "Tuma Sasa").
    Ikishindwa kuanza (Celery/broker), flush_scheduled itaichukua.
    """
    try:
        return dispatch_announcement(announcement_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
