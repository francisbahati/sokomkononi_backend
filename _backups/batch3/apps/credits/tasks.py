"""
Celery tasks for user credits.

Zeroes out credits that have passed their expiry so the frontend
stops showing stale balances.
"""

import logging

from celery import shared_task
from django.utils import timezone

from .models import UserCredit, UserService


logger = logging.getLogger(__name__)


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
