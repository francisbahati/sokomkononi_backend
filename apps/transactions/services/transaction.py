
from django.db import transaction as db_transaction
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from apps.deals.models import DealRoom
from apps.listings.models import Listing

from ..models import InspectionPeriod, Reservation, Transaction

from .notifications import (
    notify_buyer_decision,
    notify_payment_confirmed,
    notify_payment_proof_uploaded,
    notify_transaction_cancelled,
    notify_transaction_completed,
    notify_transaction_created,
)


# ============================================================================
# CREATE TRANSACTION
# ============================================================================

@db_transaction.atomic
def create_transaction_from_deal_room(*, deal_room, user):
    """
    Create a Transaction from an AGREED Deal Room.

    The Deal Room is the source of truth for:

        - buyer
        - seller
        - listing
        - agreed price

    The client cannot override any of these values.
    """

    if not user or not user.is_authenticated:
        raise ValidationError(
            "Lazima uwe umeingia kwenye akaunti."
        )

    if not user.is_active or not user.is_verified:
        raise ValidationError(
            "Akaunti yako lazima iwe active na imethibitishwa."
        )

    if deal_room.status != DealRoom.Status.AGREED:
        raise ValidationError(
            "Transaction inaweza kuundwa tu baada ya Deal Room "
            "kukubaliana bei."
        )

    if deal_room.agreed_price is None:
        raise ValidationError(
            "Deal Room haina bei iliyokubaliwa."
        )

    if user.id not in [
        deal_room.buyer_id,
        deal_room.seller_id,
    ]:
        raise ValidationError(
            "Huruhusiwi kuunda Transaction ya Deal Room hii."
        )

    existing_transaction = (
        Transaction.objects
        .select_for_update()
        .filter(
            deal_room=deal_room,
        )
        .first()
    )

    if existing_transaction:
        raise ValidationError(
            "Transaction tayari imeundwa kwa Deal Room hii."
        )

    listing = (
        Listing.objects
        .select_for_update()
        .get(
            pk=deal_room.listing_id,
        )
    )

    if listing.status != Listing.Status.AVAILABLE:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya AVAILABLE."
        )

    transaction = Transaction.objects.create(
        deal_room=deal_room,
        listing=listing,
        buyer=deal_room.buyer,
        seller=deal_room.seller,
        agreed_price=deal_room.agreed_price,
        status=Transaction.Status.RESERVATION_PENDING,
    )

    # ------------------------------------------------------------------------
    # NOTIFICATION
    # ------------------------------------------------------------------------

    notify_transaction_created(
        transaction=transaction,
    )

    return transaction


# ============================================================================
# BUYER DECISION
# ============================================================================

@db_transaction.atomic
def submit_buyer_decision(
    *,
    transaction,
    buyer,
    decision,
    note="",
):
    """
    Save the buyer's decision after inspection.
    """

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related(
            "listing",
            "buyer",
            "seller",
        )
        .get(
            pk=transaction.pk,
        )
    )

    if buyer.id != transaction.buyer_id:
        raise ValidationError(
            "Uamuzi huu unaweza kufanywa na mnunuzi pekee."
        )

    if transaction.status != Transaction.Status.INSPECTION:
        raise ValidationError(
            "Uamuzi unaweza kufanywa wakati wa inspection pekee."
        )

    valid_decisions = {
        Transaction.BuyerDecision.READY_FOR_FINAL_PAYMENT,
        Transaction.BuyerDecision.NOT_AS_DESCRIBED,
        Transaction.BuyerDecision.REQUEST_NEGOTIATION,
        Transaction.BuyerDecision.CANCEL_TRANSACTION,
    }

    if decision not in valid_decisions:
        raise ValidationError(
            "Uamuzi wa mnunuzi si sahihi."
        )

    note = (note or "").strip()

    if decision in {
        Transaction.BuyerDecision.NOT_AS_DESCRIBED,
        Transaction.BuyerDecision.REQUEST_NEGOTIATION,
        Transaction.BuyerDecision.CANCEL_TRANSACTION,
    } and not note:
        raise ValidationError(
            "Tafadhali toa maelezo ya uamuzi wako."
        )

    now = timezone.now()

    transaction.buyer_decision = decision
    transaction.buyer_decision_note = note
    transaction.buyer_decision_at = now

    if decision == Transaction.BuyerDecision.READY_FOR_FINAL_PAYMENT:

        transaction.status = (
            Transaction.Status.READY_FOR_FINAL_PAYMENT
        )

    elif decision == Transaction.BuyerDecision.NOT_AS_DESCRIBED:

        transaction.status = Transaction.Status.DISPUTED

    elif decision == Transaction.BuyerDecision.REQUEST_NEGOTIATION:

        transaction.status = Transaction.Status.DISPUTED

    elif decision == Transaction.BuyerDecision.CANCEL_TRANSACTION:

        transaction.status = Transaction.Status.CANCELLED
        transaction.cancelled_at = now
        transaction.cancellation_reason = note

        transaction.listing.status = Listing.Status.AVAILABLE

        transaction.listing.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    transaction.save()

    # ------------------------------------------------------------------------
    # NOTIFICATION
    # ------------------------------------------------------------------------

    notify_buyer_decision(
        transaction=transaction,
    )

    return transaction


# ============================================================================
# UPLOAD FINAL PAYMENT PROOF
# ============================================================================

@db_transaction.atomic
def upload_final_payment_proof(
    *,
    transaction,
    buyer,
    proof,
    payment_reference="",
):
    """
    Buyer uploads proof that the final balance was paid directly
    to the seller.
    """

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related(
            "listing",
            "buyer",
            "seller",
        )
        .get(
            pk=transaction.pk,
        )
    )

    if buyer.id != transaction.buyer_id:
        raise ValidationError(
            "Ushahidi wa malipo unaweza kupakiwa na mnunuzi pekee."
        )

    if transaction.status != Transaction.Status.READY_FOR_FINAL_PAYMENT:
        raise ValidationError(
            "Transaction haipo tayari kwa malipo ya mwisho."
        )

    if not proof:
        raise ValidationError(
            "Ushahidi wa malipo unahitajika."
        )

    max_size = 10 * 1024 * 1024

    if proof.size > max_size:
        raise ValidationError(
            "Faili haliwezi kuzidi 10MB."
        )

    transaction.final_payment_proof = proof

    transaction.final_payment_reference = (
        payment_reference or ""
    ).strip()

    transaction.final_payment_uploaded_at = timezone.now()

    transaction.save(
        update_fields=[
            "final_payment_proof",
            "final_payment_reference",
            "final_payment_uploaded_at",
            "updated_at",
        ]
    )

    # ------------------------------------------------------------------------
    # NOTIFICATION
    # ------------------------------------------------------------------------

    notify_payment_proof_uploaded(
        transaction=transaction,
    )

    return transaction


# ============================================================================
# SELLER CONFIRMS FINAL PAYMENT
# ============================================================================

@db_transaction.atomic
def seller_confirm_final_payment(
    *,
    transaction,
    seller,
):
    """
    Seller confirms receipt of the final payment.

    Once confirmed:

        Transaction -> COMPLETED
        Listing     -> SOLD
        Deal Room   -> CLOSED
        Reservation -> COMPLETED
        Inspection  -> COMPLETED
    """

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related(
            "listing",
            "deal_room",
            "buyer",
            "seller",
        )
        .get(
            pk=transaction.pk,
        )
    )

    if seller.id != transaction.seller_id:
        raise ValidationError(
            "Uthibitisho wa malipo unaweza kufanywa na muuzaji pekee."
        )

    if transaction.status != Transaction.Status.READY_FOR_FINAL_PAYMENT:
        raise ValidationError(
            "Transaction haipo kwenye hatua ya malipo ya mwisho."
        )

    if not transaction.final_payment_proof:
        raise ValidationError(
            "Mnunuzi bado hajapakia ushahidi wa malipo ya mwisho."
        )

    if transaction.seller_confirmed_payment:
        raise ValidationError(
            "Malipo tayari yamethibitishwa."
        )

    now = timezone.now()

    transaction.seller_confirmed_payment = True
    transaction.seller_confirmed_at = now
    transaction.status = Transaction.Status.COMPLETED
    transaction.completed_at = now

    transaction.save(
        update_fields=[
            "seller_confirmed_payment",
            "seller_confirmed_at",
            "status",
            "completed_at",
            "updated_at",
        ]
    )

    # ------------------------------------------------------------------------
    # LISTING -> SOLD
    # ------------------------------------------------------------------------

    listing = transaction.listing

    listing.status = Listing.Status.SOLD

    listing.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    # ------------------------------------------------------------------------
    # DEAL ROOM -> CLOSED
    # ------------------------------------------------------------------------

    deal_room = transaction.deal_room

    deal_room.status = DealRoom.Status.CLOSED

    deal_room.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    # ------------------------------------------------------------------------
    # RESERVATION -> COMPLETED
    # ------------------------------------------------------------------------

    reservation = getattr(
        transaction,
        "reservation",
        None,
    )

    if reservation:

        reservation.status = Reservation.Status.COMPLETED

        reservation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------------
    # INSPECTION -> COMPLETED
    # ------------------------------------------------------------------------

    inspection = getattr(
        transaction,
        "inspection_period",
        None,
    )

    if inspection:

        inspection.status = InspectionPeriod.Status.COMPLETED
        inspection.completed_at = now

        inspection.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------------
    # NOTIFICATIONS
    # ------------------------------------------------------------------------

    # Seller confirmed final payment -> notify buyer.
    notify_payment_confirmed(
        transaction=transaction,
    )

    # Transaction completely finished -> notify both.
    notify_transaction_completed(
        transaction=transaction,
    )

    return transaction


# ============================================================================
# CANCEL TRANSACTION
# ============================================================================

@db_transaction.atomic
def cancel_transaction(
    *,
    transaction,
    user,
    reason,
):
    """
    Cancel an eligible transaction.

    Listing is returned to AVAILABLE unless another business rule
    later requires administrative/dispute handling.
    """

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related(
            "listing",
            "deal_room",
            "buyer",
            "seller",
        )
        .get(
            pk=transaction.pk,
        )
    )

    if user.id not in [
        transaction.buyer_id,
        transaction.seller_id,
    ] and not user.is_staff:
        raise ValidationError(
            "Huruhusiwi kughairi Transaction hii."
        )

    if transaction.status in [
        Transaction.Status.COMPLETED,
        Transaction.Status.CANCELLED,
    ]:
        raise ValidationError(
            "Transaction hii haiwezi kughairiwa tena."
        )

    reason = (reason or "").strip()

    if not reason:
        raise ValidationError(
            "Sababu ya kughairi inahitajika."
        )

    now = timezone.now()

    transaction.status = Transaction.Status.CANCELLED
    transaction.cancelled_at = now
    transaction.cancellation_reason = reason

    transaction.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "updated_at",
        ]
    )

    # ------------------------------------------------------------------------
    # LISTING -> AVAILABLE
    # ------------------------------------------------------------------------

    listing = transaction.listing

    if listing.status == Listing.Status.RESERVED:

        listing.status = Listing.Status.AVAILABLE

        listing.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------------
    # DEAL ROOM -> CANCELLED
    # ------------------------------------------------------------------------

    deal_room = transaction.deal_room

    if deal_room.status != DealRoom.Status.CLOSED:

        deal_room.status = DealRoom.Status.CANCELLED

        deal_room.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------------
    # RESERVATION -> CANCELLED
    # ------------------------------------------------------------------------

    reservation = getattr(
        transaction,
        "reservation",
        None,
    )

    if reservation and reservation.status in [
        Reservation.Status.PENDING_PAYMENT,
        Reservation.Status.ACTIVE,
    ]:

        reservation.status = Reservation.Status.CANCELLED

        reservation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------------
    # INSPECTION -> CANCELLED
    # ------------------------------------------------------------------------

    inspection = getattr(
        transaction,
        "inspection_period",
        None,
    )

    if inspection and inspection.status in [
        InspectionPeriod.Status.PENDING,
        InspectionPeriod.Status.ACTIVE,
    ]:

        inspection.status = InspectionPeriod.Status.CANCELLED

        inspection.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------------
    # NOTIFICATION
    # ------------------------------------------------------------------------

    # Only notify the other participant when cancellation
    # was performed by buyer or seller.
    if user.id in [
        transaction.buyer_id,
        transaction.seller_id,
    ]:

        notify_transaction_cancelled(
            transaction=transaction,
            cancelled_by=user,
            reason=reason,
        )

    return transaction
