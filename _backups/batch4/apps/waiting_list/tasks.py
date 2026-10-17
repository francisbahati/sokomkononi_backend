"""Celery tasks for the waiting list."""
import logging
from celery import shared_task
from django.utils import timezone

from .models import WaitingListEntry

logger = logging.getLogger(__name__)


@shared_task(name="waiting_list.expire_notified")
def expire_notified():
    now = timezone.now()
    expired = list(WaitingListEntry.objects.filter(
        status=WaitingListEntry.Status.NOTIFIED,
        respond_by__lt=now,
    ))

    listing_ids = set()
    for entry in expired:
        listing_ids.add(entry.listing_id)
        entry.status = WaitingListEntry.Status.CANCELLED
        entry.save(update_fields=["status", "updated_at"])

    # Notify next-in-queue for each affected listing
    for listing_id in listing_ids:
        try:
            from apps.listings.models import Listing
            from .services.notifications import notify_waiting_buyers
            listing = Listing.objects.filter(pk=listing_id).first()
            if listing and listing.status == Listing.Status.LIVE:
                notify_waiting_buyers(listing=listing)
        except Exception:
            logger.exception("cascade failed for listing %s", listing_id)

    logger.info("waiting_list.expire_notified: expired=%s", len(expired))
    return {"expired": len(expired)}
