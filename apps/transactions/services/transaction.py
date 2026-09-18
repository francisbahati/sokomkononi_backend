from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.deals.models import DealRoom
from apps.listings.models import Listing
from apps.waiting_list.services.notifications import notify_waiting_buyers

from ..models import InspectionPeriod, Reservation, Transaction
from .notifications import (
    notify_buyer_decision,
    notify_payment_confirmed,
    notify_payment_proof_uploaded,
    notify_transaction_cancelled,
    notify_transaction_completed,
    notify_transaction_created,
)


@db_transaction.atomic
def create_transaction_from_deal_room(*, deal_room, user):
    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
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
        raise ValidationError("Deal Room haina bei iliyokubaliwa.")
    if user.id not in [deal_room.buyer_id, deal_room.seller_id]:
        raise ValidationError(
            "Huruhusiwi kuunda Transaction ya Deal Room hii."
        )

    if Transaction.objects.select_for_update().filter(
        deal_room=deal_room,
    ).exists():
        raise ValidationError(
            "Transaction tayari imeundwa kwa Deal Room hii."
        )

    listing = Listing.objects.select_for_update().get(
        pk=deal_room.listing_id,
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

    db_transaction.on_commit(
        lambda: notify_transaction_created(transaction=transaction)
    )
    return transaction


@db_transaction.atomic
def submit_buyer_decision(*, transaction, buyer, decision, note=""):
    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "buyer", "seller")
        .get(pk=transaction.pk)
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
        raise ValidationError("Uamuzi wa mnunuzi si sahihi.")

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
        transaction.status = Transaction.Status.READY_FOR_FINAL_PAYMENT
    elif decision in {
        Transaction.BuyerDecision.NOT_AS_DESCRIBED,
        Transaction.BuyerDecision.REQUEST_NEGOTIATION,
    }:
        transaction.status = Transaction.Status.DISPUTED
    elif decision == Transaction.BuyerDecision.CANCEL_TRANSACTION:
        transaction.status = Transaction.Status.CANCELLED
        transaction.cancelled_at = now
        transaction.cancellation_reason = note

        listing = Listing.objects.select_for_update().get(
            pk=transaction.listing_id,
        )
        if listing.status in [
            Listing.Status.RESERVED, Listing.Status.SOLD,
        ]:
            listing.status = Listing.Status.AVAILABLE
            listing.save(update_fields=["status", "updated_at"])

    transaction.save()
    db_transaction.on_commit(
        lambda: notify_buyer_decision(transaction=transaction)
    )
    return transaction


@db_transaction.atomic
def upload_final_payment_proof(
    *, transaction, buyer, proof, payment_reference="",
):
    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "buyer", "seller")
        .get(pk=transaction.pk)
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
        raise ValidationError("Ushahidi wa malipo unahitajika.")
    if proof.size > 10 * 1024 * 1024:
        raise ValidationError("Faili haliwezi kuzidi 10MB.")

    transaction.final_payment_proof = proof
    transaction.final_payment_reference = (payment_reference or "").strip()
    transaction.final_payment_uploaded_at = timezone.now()
    transaction.save(update_fields=[
        "final_payment_proof", "final_payment_reference",
        "final_payment_uploaded_at", "updated_at",
    ])

    db_transaction.on_commit(
        lambda: notify_payment_proof_uploaded(transaction=transaction)
    )
    return transaction


@db_transaction.atomic
def seller_confirm_final_payment(*, transaction, seller):
    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "deal_room", "buyer", "seller")
        .get(pk=transaction.pk)
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
        raise ValidationError("Malipo tayari yamethibitishwa.")

    inspection = getattr(transaction, "inspection_period", None)
    if inspection and inspection.status != InspectionPeriod.Status.COMPLETED:
        raise ValidationError(
            "Inspection period bado haijakamilika."
        )

    now = timezone.now()
    transaction.seller_confirmed_payment = True
    transaction.seller_confirmed_at = now
    transaction.status = Transaction.Status.COMPLETED
    transaction.completed_at = now
    transaction.save(update_fields=[
        "seller_confirmed_payment", "seller_confirmed_at",
        "status", "completed_at", "updated_at",
    ])

    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )
    listing.status = Listing.Status.SOLD
    listing.save(update_fields=["status", "updated_at"])

    deal_room = DealRoom.objects.select_for_update().get(
        pk=transaction.deal_room_id,
    )
    deal_room.status = DealRoom.Status.CLOSED
    deal_room.save(update_fields=["status", "updated_at"])

    reservation = getattr(transaction, "reservation", None)
    if reservation:
        reservation.status = Reservation.Status.COMPLETED
        reservation.save(update_fields=["status", "updated_at"])

    if inspection:
        inspection.status = InspectionPeriod.Status.COMPLETED
        inspection.completed_at = now
        inspection.save(
            update_fields=["status", "completed_at", "updated_at"],
        )

    db_transaction.on_commit(lambda: _fire_completion_side_effects(
        transaction=transaction, listing=listing,
    ))
    return transaction


def _fire_completion_side_effects(*, transaction, listing):
    try:
        notify_payment_confirmed(transaction=transaction)
        notify_transaction_completed(transaction=transaction)
    except Exception:
        pass

    # Waiting-list hook (only if listing has entries)
    try:
        notify_waiting_buyers(listing=listing)
    except Exception:
        pass


@db_transaction.atomic
def cancel_transaction(*, transaction, user, reason):
    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "deal_room", "buyer", "seller")
        .get(pk=transaction.pk)
    )

    if user.id not in [transaction.buyer_id, transaction.seller_id] \
            and not user.is_staff:
        raise ValidationError("Huruhusiwi kughairi Transaction hii.")

    if transaction.status in [
        Transaction.Status.COMPLETED, Transaction.Status.CANCELLED,
    ]:
        raise ValidationError("Transaction hii haiwezi kughairiwa tena.")

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Sababu ya kughairi inahitajika.")

    now = timezone.now()
    transaction.status = Transaction.Status.CANCELLED
    transaction.cancelled_at = now
    transaction.cancellation_reason = reason
    transaction.save(update_fields=[
        "status", "cancelled_at", "cancellation_reason", "updated_at",
    ])

    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )
    listing_was_reopened = False
    if listing.status in [Listing.Status.RESERVED, Listing.Status.SOLD]:
        listing.status = Listing.Status.AVAILABLE
        listing.save(update_fields=["status", "updated_at"])
        listing_was_reopened = True

    deal_room = DealRoom.objects.select_for_update().get(
        pk=transaction.deal_room_id,
    )
    if deal_room.status != DealRoom.Status.CLOSED:
        deal_room.status = DealRoom.Status.CANCELLED
        deal_room.save(update_fields=["status", "updated_at"])

    reservation = getattr(transaction, "reservation", None)
    if reservation and reservation.status in [
        Reservation.Status.PENDING_PAYMENT, Reservation.Status.ACTIVE,
    ]:
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])

    inspection = getattr(transaction, "inspection_period", None)
    if inspection and inspection.status in [
        InspectionPeriod.Status.PENDING, InspectionPeriod.Status.ACTIVE,
    ]:
        inspection.status = InspectionPeriod.Status.CANCELLED
        inspection.save(update_fields=["status", "updated_at"])

    if user.id in [transaction.buyer_id, transaction.seller_id]:
        db_transaction.on_commit(
            lambda: notify_transaction_cancelled(
                transaction=transaction,
                cancelled_by=user,
                reason=reason,
            )
        )

    if listing_was_reopened:
        db_transaction.on_commit(
            lambda: notify_waiting_buyers(listing=listing)
        )

    return transaction