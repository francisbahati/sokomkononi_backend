"""Celery tasks for the boosting app."""
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import ListingBoost

logger = logging.getLogger(__name__)


@shared_task(name="boosting.expire_stale_boosts")
def expire_stale_boosts():
    """
    Move every ACTIVE boost past its expiry to EXPIRED and clear the
    listing-level boost flag when no active boost remains.

    Batched: one UPDATE for boost statuses, one UPDATE for the affected
    listings — no per-row transactions.
    """
    now = timezone.now()
    expired_qs = ListingBoost.objects.filter(
        status=ListingBoost.BoostStatus.ACTIVE,
        expires_at__lt=now,
    )

    listing_ids = list(expired_qs.values_list("listing_id", flat=True).distinct())
    if not listing_ids:
        return {"expired": 0}

    with transaction.atomic():
        expired_count = expired_qs.update(
            status=ListingBoost.BoostStatus.EXPIRED,
            updated_at=now,
        )
        from apps.listings.models import Listing
        Listing.objects.filter(
            pk__in=listing_ids,
            boosted_until__lte=now,
        ).update(is_boosted=False, boosted_until=None, updated_at=now)

    logger.info("expire_stale_boosts: expired=%s", expired_count)
    return {"expired": expired_count}
