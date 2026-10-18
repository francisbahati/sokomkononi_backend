"""Celery tasks for the listings app."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Listing

logger = logging.getLogger(__name__)


@shared_task(name="listings.expire_stale_listings")
def expire_stale_listings():
    """Archive LIVE listings older than PlatformPolicy.listing_lifetime_days."""
    try:
        from apps.system_settings.models import PlatformPolicy
        days = PlatformPolicy.get_solo().listing_lifetime_days
    except Exception:
        days = 60

    cutoff = timezone.now() - timedelta(days=days)
    count = Listing.objects.filter(
        status=Listing.Status.LIVE,
        created_at__lt=cutoff,
    ).update(
        status=Listing.Status.ARCHIVED,
        updated_at=timezone.now(),
    )
    logger.info("expire_stale_listings: archived=%s", count)
    return {"archived": count}
