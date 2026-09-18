"""
Notifications for the waiting list.

When a listing becomes AVAILABLE again, every WAITING buyer is
notified and their entry is marked NOTIFIED.
"""

import logging

from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import WaitingListEntry


logger = logging.getLogger(__name__)


def notify_waiting_buyers(*, listing):
    """
    Mark every WAITING entry as NOTIFIED and send a notification
    to each buyer.
    """
    entries = list(
        WaitingListEntry.objects
        .filter(
            listing=listing,
            status=WaitingListEntry.Status.WAITING,
        )
        .select_related("buyer")
        .order_by("position", "joined_at")
    )

    if not entries:
        return []

    now = timezone.now()

    for entry in entries:
        entry.status = WaitingListEntry.Status.NOTIFIED
        entry.notified_at = now
        entry.save(
            update_fields=["status", "notified_at", "updated_at"]
        )

        try:
            create_notification(
                recipient=entry.buyer,
                notification_type=(
                    Notification.NotificationType
                    .WAITING_LIST_AVAILABLE
                ),
                title="Tangazo limepatikana tena",
                message=(
                    f"Tangazo '{listing.title}' ulilokuwa ukisubiri "
                    f"sasa linapatikana tena. Ingia haraka kabla "
                    f"halijachukuliwa."
                ),
                priority=Notification.Priority.URGENT,
                related_object_type="Listing",
                related_object_id=listing.id,
                action_url=f"/listings/{listing.id}/",
            )
        except Exception:
            logger.exception(
                "Failed to notify waiting-list buyer %s for listing %s",
                entry.buyer_id,
                listing.id,
            )

    return entries