"""
Celery tasks for banner ads.

Deactivates banners that have passed their expiry.
"""

import logging

from celery import shared_task
from django.utils import timezone

from .models import BannerAd


logger = logging.getLogger(__name__)


@shared_task(name="banners.expire_stale_banners")
def expire_stale_banners():
    now = timezone.now()
    qs = BannerAd.objects.filter(active=True, expires_at__lt=now)
    count = qs.update(active=False)
    logger.info("expire_stale_banners: deactivated %s banners", count)
    return {"deactivated": count}
