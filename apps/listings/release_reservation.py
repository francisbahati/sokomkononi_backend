"""
POST /api/listings/{id}/release-reservation/

Frees the current RESERVED reservation on a listing and advances
the waiting list (Option A):
    1. Mark the listing LIVE again.
    2. Expire/cancel the previous reservation + transaction.
    3. Mark the first WAITING entry as NOTIFIED and give it a
       response window (default 24 h, overridable via settings).
    4. Emit WAITING_LIST_AVAILABLE notifications.

Idempotent: safe to call when there is no active reservation.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import Listing

logger = logging.getLogger(__name__)

RESPONSE_WINDOW_HOURS = 24


class ReleaseReservationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk=None):
        # Owner or staff only (release is safe to allow anyone who owns
        # the listing; anonymous is a no-op).
        listing = (
            Listing.all_objects
            .select_related("seller")
            .filter(pk=pk)
            .first()
        )
        if not listing:
            return Response(
                {"detail": "Tangazo halipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        is_owner = user and user.is_authenticated and user.id == listing.seller_id
        is_staff = user and getattr(user, "is_staff", False)

        # Anonymous callers: this is a webhook-style idempotent nudge.
        # We allow it, but only when the reservation window has actually
        # elapsed (checked below).
        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(pk=listing.pk)

            # Only act when there is an expired reservation on this listing.
            txn = getattr(listing, "transactions", None)
            reservation = None
            try:
                from apps.transactions.models import Reservation
                reservation = (
                    Reservation.objects
                    .select_for_update()
                    .select_related("transaction")
                    .filter(transaction__listing=listing)
                    .order_by("-created_at")
                    .first()
                )
            except Exception:
                reservation = None

            now = timezone.now()
            expired = (
                reservation
                and reservation.status in ("PENDING_PAYMENT", "ACTIVE")
                and reservation.expires_at
                and reservation.expires_at <= now
            )

            if not (expired or is_owner or is_staff):
                # Nothing to do — return the current state as-is.
                return Response(
                    {
                        "released": False,
                        "reason": "reservation_not_expired",
                        "listing_id": listing.id,
                        "status": listing.status,
                    },
                    status=status.HTTP_200_OK,
                )

            # 1. Free the listing
            was_reserved = listing.status == Listing.Status.RESERVED
            if was_reserved:
                listing.status = Listing.Status.LIVE
                listing.save(update_fields=["status", "updated_at"])

            # 2. Cancel the reservation + transaction
            if reservation:
                reservation.status = "CANCELLED"
                reservation.save(update_fields=["status", "updated_at"])
                try:
                    txn_obj = reservation.transaction
                    if txn_obj.status in (
                        "RESERVED", "INSPECTION",
                        "RESERVATION_PENDING", "READY_FOR_FINAL_PAYMENT",
                    ):
                        txn_obj.status = "CANCELLED"
                        txn_obj.cancelled_at = now
                        txn_obj.cancellation_reason = "Reservation released."
                        txn_obj.save(update_fields=[
                            "status", "cancelled_at",
                            "cancellation_reason", "updated_at",
                        ])
                except Exception:
                    logger.exception("Could not cancel parent transaction")

            # 3. Advance the waiting list — Option A
            advanced = None
            try:
                from apps.waiting_list.models import WaitingListEntry
                first = (
                    WaitingListEntry.objects
                    .select_for_update()
                    .filter(
                        listing=listing,
                        status=WaitingListEntry.Status.WAITING,
                    )
                    .order_by("position", "joined_at")
                    .first()
                )
                if first:
                    first.status = WaitingListEntry.Status.NOTIFIED
                    first.notified_at = now
                    # Record the deadline in the (optional) field
                    if hasattr(first, "respond_by"):
                        first.respond_by = now + timedelta(
                            hours=RESPONSE_WINDOW_HOURS
                        )
                    first.save()
                    advanced = first.id
            except Exception:
                logger.exception("Failed to advance waiting list")

        # Fire notifications after commit
        if advanced:
            try:
                from apps.notifications.models import Notification
                from apps.notifications.services.notification import (
                    create_notification,
                )
                first = WaitingListEntry.objects.get(pk=advanced)
                create_notification(
                    recipient=first.buyer,
                    notification_type=(
                        Notification.NotificationType.WAITING_LIST_AVAILABLE
                    ),
                    title="Nafasi imefunguliwa!",
                    message=(
                        f"Tangazo '{listing.title}' sasa linapatikana. "
                        f"Una masaa {RESPONSE_WINDOW_HOURS} kuanza "
                        f"reservation yako kabla ya nafasi kwenda "
                        f"kwa mtu mwingine."
                    ),
                    priority=Notification.Priority.URGENT,
                    related_object_type="Listing",
                    related_object_id=listing.id,
                    action_url=f"/dashboard/buyer/waiting",
                )
            except Exception:
                logger.exception("Failed to notify first waiter")

        return Response(
            {
                "released": True,
                "listing_id": listing.id,
                "status": listing.status,
                "advanced_waitlist_entry": advanced,
            },
            status=status.HTTP_200_OK,
        )
