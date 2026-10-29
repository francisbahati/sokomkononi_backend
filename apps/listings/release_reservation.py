"""
POST /api/listings/{id}/release-reservation/

Inarudisha mali hewani na kuendeleza waiting list (Option A).

Mtiririko:
    1. Tumia release_reserved_listing() — inaghairi transaction,
       deal, reservation na kuweka listing LIVE.
    2. Mwalike mwanzo kwenye waiting list (NOTIFIED + response window).
    3. Tuma notification ya WAITING_LIST_AVAILABLE.

Idempotent: salama kuita wakati hakuna reservation hai.
"""
import logging
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import Listing
from apps.listings.serializers import ListingDetailSerializer
from apps.transactions.services.transaction import release_reserved_listing
from apps.waiting_list.constants import RESPONSE_WINDOW_HOURS

logger = logging.getLogger(__name__)


class ReleaseReservationView(APIView):
    """Admin-only: rudisha mali hewani + endeleza waiting list."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk=None):
        reason = (request.data.get("reason") or "").strip()

        try:
            listing = release_reserved_listing(
                listing_id=pk,
                admin_user=request.user,
                reason=reason,
            )
        except Listing.DoesNotExist:
            return Response(
                {"detail": "Tangazo halipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            msg = getattr(exc, "messages", [str(exc)])
            return Response(
                {"detail": msg[0] if isinstance(msg, list) else msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Waiting list advancement (Option A) ──
        advanced_id = None
        try:
            from apps.waiting_list.models import WaitingListEntry

            with transaction.atomic():
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
                    now = timezone.now()
                    first.status = WaitingListEntry.Status.NOTIFIED
                    first.notified_at = now
                    if hasattr(first, "respond_by"):
                        first.respond_by = now + timedelta(
                            hours=RESPONSE_WINDOW_HOURS
                        )
                    first.save()
                    advanced_id = first.id
        except Exception:
            logger.exception("Waiting-list advancement failed")

        # ── Notify first waiter ──
        if advanced_id:
            try:
                from apps.waiting_list.models import WaitingListEntry
                from apps.notifications.models import Notification
                from apps.notifications.services.notification import (
                    create_notification,
                )

                entry = WaitingListEntry.objects.get(pk=advanced_id)
                create_notification(
                    recipient=entry.buyer,
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
                    action_url="/dashboard/buyer/waiting",
                )
            except Exception:
                logger.exception("Failed to notify first waiter")

        return Response(
            {
                "released": True,
                "listing_id": listing.id,
                "status": listing.status,
                "advanced_waitlist_entry": advanced_id,
                "listing": ListingDetailSerializer(
                    listing, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )