"""
Celery tasks for the transactions app.

Drives time-based transitions:

    - ACTIVE reservations past their expiry are moved to EXPIRED,
      cascading the parent transaction to CANCELLED.
    - ACTIVE inspection periods past their expiry are completed,
      moving the parent transaction to DISPUTED when the buyer
      has not submitted a decision.
    - ACTIVE reservations approaching their expiry trigger a
      warning notification so the buyer can act in time.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from .models import InspectionPeriod, Reservation
from .services.reservation import (
    expire_inspection_period,
    expire_reservation,
)


logger = logging.getLogger(__name__)


RESERVATION_WARNING_HOURS = 6


@shared_task(name="transactions.expire_stale_reservations")
def expire_stale_reservations():
    """
    Expire every ACTIVE reservation whose `expires_at` has passed.
    """
    now = timezone.now()

    reservation_ids = list(
        Reservation.objects
        .filter(
            status=Reservation.Status.ACTIVE,
            expires_at__lt=now,
        )
        .values_list("pk", flat=True)
    )

    expired = 0
    failed = 0

    for reservation_id in reservation_ids:
        try:
            reservation = Reservation.objects.get(pk=reservation_id)
            expire_reservation(reservation=reservation)
            expired += 1
        except Exception:
            failed += 1
            logger.exception(
                "Failed to expire reservation %s", reservation_id
            )

    logger.info(
        "expire_stale_reservations: expired=%s failed=%s",
        expired,
        failed,
    )
    return {"expired": expired, "failed": failed}


@shared_task(name="transactions.expire_stale_inspections")
def expire_stale_inspections():
    """
    Complete every ACTIVE inspection whose `expires_at` has passed.
    """
    now = timezone.now()

    inspection_ids = list(
        InspectionPeriod.objects
        .filter(
            status=InspectionPeriod.Status.ACTIVE,
            expires_at__lt=now,
        )
        .values_list("pk", flat=True)
    )

    expired = 0
    failed = 0

    for inspection_id in inspection_ids:
        try:
            inspection = InspectionPeriod.objects.get(pk=inspection_id)
            expire_inspection_period(inspection=inspection)
            expired += 1
        except Exception:
            failed += 1
            logger.exception(
                "Failed to expire inspection %s", inspection_id
            )

    logger.info(
        "expire_stale_inspections: expired=%s failed=%s",
        expired,
        failed,
    )
    return {"expired": expired, "failed": failed}


@shared_task(name="transactions.warn_expiring_reservations")
def warn_expiring_reservations():
    """
    Notify buyers whose ACTIVE reservation expires within
    RESERVATION_WARNING_HOURS. Skips if already warned.
    """
    now = timezone.now()
    cutoff = now + timedelta(hours=RESERVATION_WARNING_HOURS)

    reservations = list(
        Reservation.objects
        .filter(
            status=Reservation.Status.ACTIVE,
            expires_at__gte=now,
            expires_at__lte=cutoff,
        )
        .select_related(
            "transaction",
            "transaction__buyer",
            "transaction__listing",
        )
    )

    warned = 0

    for reservation in reservations:
        transaction = reservation.transaction

        already_warned = Notification.objects.filter(
            recipient=transaction.buyer,
            notification_type=(
                Notification.NotificationType.RESERVATION_EXPIRING
            ),
            related_object_type="Reservation",
            related_object_id=reservation.id,
        ).exists()

        if already_warned:
            continue

        hours_left = max(
            1,
            int(
                (reservation.expires_at - now).total_seconds() / 3600
            ),
        )

        create_notification(
            recipient=transaction.buyer,
            notification_type=(
                Notification.NotificationType.RESERVATION_EXPIRING
            ),
            title="Reservation inakaribia kuisha",
            message=(
                f"Reservation yako ya Transaction #{transaction.id} "
                f"ya '{transaction.listing.title}' inaisha baada ya "
                f"saa {hours_left}. Tafadhali kamilisha hatua "
                f"zinazofuata."
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="Reservation",
            related_object_id=reservation.id,
            action_url=f"/transactions/{transaction.id}",
        )

        warned += 1

    logger.info("warn_expiring_reservations: warned=%s", warned)
    return {"warned": warned}