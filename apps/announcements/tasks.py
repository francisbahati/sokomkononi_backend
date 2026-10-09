"""Celery tasks for scheduled announcements."""
import logging

from celery import shared_task
from django.utils import timezone

from .models import Announcement

logger = logging.getLogger(__name__)


@shared_task(name="announcements.flush_scheduled")
def flush_scheduled():
    """Flip `sent=True` for announcements whose scheduled_for has arrived."""
    now = timezone.now()
    updated = Announcement.objects.filter(
        sent=False,
        scheduled_for__isnull=False,
        scheduled_for__lte=now,
    ).update(sent=True)
    logger.info("announcements.flush_scheduled: %s sent", updated)
    return {"sent": updated}
