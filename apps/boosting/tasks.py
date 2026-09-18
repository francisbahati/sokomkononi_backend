"""
Celery tasks for the boosting app.

Deactivates boosts that have passed their expiry and clears the
listing-level boost flag when no active boost remains.
"""

import logging

from celery import shared_task
from django.utils import timezone

from .models import ListingBoost
from .services.boost import expire_boost


logger = logging.getLogger(__name__)


@shared_task(name="boosting.expire_stale_boosts")
def expire_stale_boosts():
    """
    Move every ACTIVE boost past its expiry to EXPIRED.
    """
    now = timezone.now()

    boost_ids = list(
        ListingBoost.objects
        .filter(
            status=ListingBoost.BoostStatus.ACTIVE,
            expires_at__lt=now,
        )
        .values_list("pk", flat=True)
    )

    expired = 0
    failed = 0

    for boost_id in boost_ids:
        try:
            boost = ListingBoost.objects.get(pk=boost_id)
            expire_boost(boost=boost)
            expired += 1
        except Exception:
            failed += 1
            logger.exception("Failed to expire boost %s", boost_id)

    logger.info(
        "expire_stale_boosts: expired=%s failed=%s", expired, failed
    )
    return {"expired": expired, "failed": failed}