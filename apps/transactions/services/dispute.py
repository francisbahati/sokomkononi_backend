"""
Dispute resolution for transactions.

A transaction can enter DISPUTED status from:

    - submit_buyer_decision (NOT_AS_DESCRIBED / REQUEST_NEGOTIATION)
    - expire_inspection_period (buyer never submitted a decision)

Only an admin can move a transaction out of DISPUTED:

    - COMPLETED: deal is honoured; listing -> SOLD
    - CANCELLED: deal is cancelled; listing -> AVAILABLE
"""

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.deals.models import DealRoom
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import InspectionPeriod, Reservation, Transaction


RESOLUTION_COMPLETED = "COMPLETED"
RESOLUTION_CANCELLED = "CANCELLED"

VALID_RESOLUTIONS = {RESOLUTION_COMPLETED, RESOLUTION_CANCELLED}


@db_transaction.atomic
def resolve_dispute(
    *,
    transaction,
    admin_user,
    resolution,
    note="",
):
    """
    Resolve a DISPUTED transaction. Staff-only.
    """
    if not admin_user or not admin_user.is_authenticated:
        raise ValidationError(
            "Lazima uwe umeingia kwenye akaunti."
        )

    if not admin_user.is_staff:
        raise ValidationError(
            "Ni wasimamizi pekee wanaoweza kutatua mgogoro."
        )

    if resolution not in VALID_RESOLUTIONS:
        raise ValidationError(
            "Uamuzi wa mgogoro si sahihi. "
            "Tumia COMPLETED au CANCELLED."
        )

    note = (note or "").strip()

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related(
            "listing",
            "deal_room",
            "buyer",
            "seller",
        )
        .get(pk=transaction.pk)
    )

    if transaction.status != Transaction.Status.DISPUTED:
        raise ValidationError(
            "Transaction hii haipo kwenye hali ya mgogoro."
        )

    now = timezone.now()

    if resolution == RESOLUTION_COMPLETED:
        _resolve_as_completed(
            transaction=transaction,
            note=note,
            now=now,
            admin_user=admin_user,
        )
    else:
        _resolve_as_cancelled(
            transaction=transaction,
            note=note,
            now=now,
            admin_user=admin_user,
        )

    transaction.save()
    return transaction


def _resolve_as_completed(*, transaction, note, now, admin_user=None):
    transaction.status = Transaction.Status.COMPLETED
    transaction.dispute_resolved_by = admin_user
    transaction.dispute_resolution_note = note
    transaction.completed_at = now
    transaction.cancellation_reason = ""

    note_text = note or "Mgogoro umetatuliwa kwa manufaa ya mauzo."
    transaction.buyer_decision_note = (
        (transaction.buyer_decision_note + " | " + note_text)
        if transaction.buyer_decision_note
        else note_text
    )

    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id
    )
    listing.status = Listing.Status.SOLD
    listing.save(update_fields=["status", "updated_at"])

    deal_room = DealRoom.objects.select_for_update().get(
        pk=transaction.deal_room_id
    )
    deal_room.status = DealRoom.Status.CLOSED
    deal_room.save(update_fields=["status", "updated_at"])

    reservation = getattr(transaction, "reservation", None)
    if reservation:
        reservation.status = Reservation.Status.COMPLETED
        reservation.save(update_fields=["status", "updated_at"])

    inspection = getattr(transaction, "inspection_period", None)
    if inspection:
        inspection.status = InspectionPeriod.Status.COMPLETED
        inspection.completed_at = now
        inspection.save(
            update_fields=["status", "completed_at", "updated_at"]
        )

    for recipient in (transaction.buyer, transaction.seller):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.TRANSACTION_COMPLETED
            ),
            title="Mgogoro umetatuliwa — Transaction imekamilika",
            message=(
                f"Mgogoro wa Transaction #{transaction.id} "
                f"umetatuliwa na msimamizi. Transaction imekamilika "
                f"na tangazo limewekwa SOLD."
            ),
            priority=Notification.Priority.URGENT,
            related_object_type="Transaction",
            related_object_id=transaction.id,
            action_url=f"/transactions/{transaction.id}",
        )


def _resolve_as_cancelled(*, transaction, note, now, admin_user=None):
    transaction.status = Transaction.Status.CANCELLED
    transaction.dispute_resolved_by = admin_user
    transaction.dispute_resolution_note = note
    transaction.cancelled_at = now
    transaction.cancellation_reason = (
        note or "Mgogoro umetatuliwa kwa kughairi muamala."
    )

    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id
    )
    if listing.status in [
        Listing.Status.RESERVED,
        Listing.Status.SOLD,
    ]:
        listing.status = Listing.Status.AVAILABLE
        listing.save(update_fields=["status", "updated_at"])

    deal_room = DealRoom.objects.select_for_update().get(
        pk=transaction.deal_room_id
    )
    if deal_room.status != DealRoom.Status.CLOSED:
        deal_room.status = DealRoom.Status.CANCELLED
        deal_room.save(update_fields=["status", "updated_at"])

    reservation = getattr(transaction, "reservation", None)
    if reservation and reservation.status in [
        Reservation.Status.PENDING_PAYMENT,
        Reservation.Status.ACTIVE,
    ]:
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])

    inspection = getattr(transaction, "inspection_period", None)
    if inspection and inspection.status in [
        InspectionPeriod.Status.PENDING,
        InspectionPeriod.Status.ACTIVE,
    ]:
        inspection.status = InspectionPeriod.Status.CANCELLED
        inspection.save(update_fields=["status", "updated_at"])

    for recipient in (transaction.buyer, transaction.seller):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.TRANSACTION_CANCELLED
            ),
            title="Mgogoro umetatuliwa — Transaction imeghairiwa",
            message=(
                f"Mgogoro wa Transaction #{transaction.id} "
                f"umetatuliwa na msimamizi. Transaction imeghairiwa "
                f"na tangazo limerudishwa kwenye hali ya AVAILABLE."
            ),
            priority=Notification.Priority.URGENT,
            related_object_type="Transaction",
            related_object_id=transaction.id,
            action_url=f"/transactions/{transaction.id}",
        )