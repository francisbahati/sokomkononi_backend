from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing
from apps.waiting_list.services.notifications import notify_waiting_buyers

from ..models import InspectionPeriod, Reservation, Transaction
from .notifications import (
    notify_inspection_completed,
    notify_inspection_started,
    notify_reservation_created,
    notify_reservation_expired,
    notify_reservation_paid,
)


DEFAULT_RESERVATION_HOURS = 48
DEFAULT_INSPECTION_HOURS = 24
RESERVATION_DEPOSIT_PERCENTAGE = Decimal("10.00")


def calculate_reservation_deposit(*, agreed_price):
    if agreed_price is None:
        raise ValidationError("Bei iliyokubaliwa haijapatikana.")

    agreed_price = Decimal(str(agreed_price))
    if agreed_price <= Decimal("0.00"):
        raise ValidationError(
            "Bei iliyokubaliwa lazima iwe kubwa kuliko sifuri."
        )

    deposit = (
        agreed_price * RESERVATION_DEPOSIT_PERCENTAGE / Decimal("100")
    )
    return deposit.quantize(Decimal("0.01"))


@db_transaction.atomic
def create_reservation(*, transaction, user, duration_hours=DEFAULT_RESERVATION_HOURS):
    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "buyer", "seller")
        .get(pk=transaction.pk)
    )

    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not user.is_active or not user.is_verified:
        raise ValidationError(
            "Akaunti yako lazima iwe active na imethibitishwa."
        )
    if user.id != transaction.buyer_id:
        raise ValidationError(
            "Reservation inaweza kuanzishwa na mnunuzi pekee."
        )
    if transaction.status != Transaction.Status.RESERVATION_PENDING:
        raise ValidationError(
            "Transaction hii haipo tayari kwa reservation."
        )
    if hasattr(transaction, "reservation"):
        raise ValidationError(
            "Reservation tayari ipo kwa Transaction hii."
        )

    # Lock and validate the listing.
    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )
    if listing.status != Listing.Status.AVAILABLE:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya AVAILABLE."
        )

    try:
        duration_hours = int(duration_hours)
    except (TypeError, ValueError):
        raise ValidationError("Muda wa reservation si sahihi.")

    if duration_hours not in [24, 48, 72]:
        raise ValidationError(
            "Reservation inaweza kuwa saa 24, 48 au 72."
        )

    deposit_amount = calculate_reservation_deposit(
        agreed_price=transaction.agreed_price,
    )

    reservation = Reservation.objects.create(
        transaction=transaction,
        deposit_amount=deposit_amount,
        duration_hours=duration_hours,
        payment_status=Reservation.PaymentStatus.PENDING,
        status=Reservation.Status.PENDING_PAYMENT,
    )

    db_transaction.on_commit(
        lambda: notify_reservation_created(reservation=reservation)
    )
    return reservation


@db_transaction.atomic
def confirm_reservation_payment(*, reservation, payment_reference):
    reservation = (
        Reservation.objects
        .select_for_update()
        .select_related(
            "transaction",
            "transaction__listing",
            "transaction__buyer",
            "transaction__seller",
        )
        .get(pk=reservation.pk)
    )

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "buyer", "seller")
        .get(pk=reservation.transaction_id)
    )

    if reservation.payment_status == Reservation.PaymentStatus.PAID:
        raise ValidationError("Reservation payment tayari imelipwa.")
    if reservation.status != Reservation.Status.PENDING_PAYMENT:
        raise ValidationError(
            "Reservation hii haipo kwenye hatua ya kusubiri malipo."
        )

    payment_reference = (payment_reference or "").strip()
    if not payment_reference:
        raise ValidationError("Payment reference inahitajika.")

    if Reservation.objects.filter(
        payment_reference=payment_reference,
    ).exclude(pk=reservation.pk).exists():
        raise ValidationError(
            "Payment reference hii tayari imetumika."
        )

    # Lock the listing row.
    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )

    if listing.status != Listing.Status.AVAILABLE:
        raise ValidationError(
            "Tangazo hili halipo tena kwenye hali ya AVAILABLE."
        )

    now = timezone.now()
    expires_at = now + timedelta(hours=reservation.duration_hours)

    reservation.payment_status = Reservation.PaymentStatus.PAID
    reservation.payment_reference = payment_reference
    reservation.paid_at = now
    reservation.starts_at = now
    reservation.expires_at = expires_at
    reservation.status = Reservation.Status.ACTIVE
    reservation.save(update_fields=[
        "payment_status", "payment_reference", "paid_at",
        "starts_at", "expires_at", "status", "updated_at",
    ])

    listing.status = Listing.Status.RESERVED
    listing.save(update_fields=["status", "updated_at"])

    transaction.status = Transaction.Status.RESERVED
    transaction.save(update_fields=["status", "updated_at"])

    db_transaction.on_commit(
        lambda: notify_reservation_paid(reservation=reservation)
    )
    return reservation


@db_transaction.atomic
def start_inspection_period(*, transaction, user, duration_hours=DEFAULT_INSPECTION_HOURS):
    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "buyer", "seller")
        .get(pk=transaction.pk)
    )

    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if user.id not in [transaction.buyer_id, transaction.seller_id] \
            and not user.is_staff:
        raise ValidationError(
            "Huruhusiwi kuanzisha inspection ya Transaction hii."
        )
    if transaction.status != Transaction.Status.RESERVED:
        raise ValidationError(
            "Inspection inaweza kuanza baada ya reservation kuwa active."
        )

    reservation = getattr(transaction, "reservation", None)
    if not reservation:
        raise ValidationError("Transaction haina Reservation.")
    if reservation.status != Reservation.Status.ACTIVE:
        raise ValidationError(
            "Reservation lazima iwe ACTIVE kabla ya inspection."
        )

    if InspectionPeriod.objects.filter(transaction=transaction).exists():
        raise ValidationError("Inspection Period tayari ipo.")

    try:
        duration_hours = int(duration_hours)
    except (TypeError, ValueError):
        raise ValidationError("Muda wa inspection si sahihi.")

    if duration_hours <= 0 or duration_hours > 168:
        raise ValidationError(
            "Inspection lazima iwe kati ya saa 1 na saa 168."
        )

    now = timezone.now()
    expires_at = now + timedelta(hours=duration_hours)

    inspection = InspectionPeriod.objects.create(
        transaction=transaction,
        duration_hours=duration_hours,
        starts_at=now,
        expires_at=expires_at,
        status=InspectionPeriod.Status.ACTIVE,
    )

    transaction.status = Transaction.Status.INSPECTION
    transaction.buyer_decision = Transaction.BuyerDecision.PENDING
    transaction.save(update_fields=[
        "status", "buyer_decision", "updated_at",
    ])

    db_transaction.on_commit(
        lambda: notify_inspection_started(inspection=inspection)
    )
    return inspection


@db_transaction.atomic
def expire_reservation(*, reservation):
    reservation = (
        Reservation.objects
        .select_for_update()
        .select_related(
            "transaction",
            "transaction__listing",
            "transaction__deal_room",
            "transaction__buyer",
            "transaction__seller",
        )
        .get(pk=reservation.pk)
    )

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("listing", "buyer", "seller")
        .get(pk=reservation.transaction_id)
    )

    now = timezone.now()

    if reservation.status != Reservation.Status.ACTIVE:
        raise ValidationError("Reservation hii haipo ACTIVE.")
    if not reservation.expires_at:
        raise ValidationError("Reservation haina muda wa kuisha.")
    if reservation.expires_at > now:
        raise ValidationError("Reservation bado haija-expire.")

    reservation.status = Reservation.Status.EXPIRED
    reservation.save(update_fields=["status", "updated_at"])

    listing_reopened = False
    if transaction.status in [
        Transaction.Status.RESERVED, Transaction.Status.INSPECTION,
    ]:
        transaction.status = Transaction.Status.CANCELLED
        transaction.cancelled_at = now
        transaction.cancellation_reason = "Reservation imeisha muda."
        transaction.save(update_fields=[
            "status", "cancelled_at", "cancellation_reason", "updated_at",
        ])

        listing = Listing.objects.select_for_update().get(
            pk=transaction.listing_id,
        )
        if listing.status == Listing.Status.RESERVED:
            listing.status = Listing.Status.AVAILABLE
            listing.save(update_fields=["status", "updated_at"])
            listing_reopened = True

    inspection = getattr(transaction, "inspection_period", None)
    if inspection and inspection.status in [
        InspectionPeriod.Status.PENDING, InspectionPeriod.Status.ACTIVE,
    ]:
        inspection.status = InspectionPeriod.Status.CANCELLED
        inspection.save(update_fields=["status", "updated_at"])

    db_transaction.on_commit(
        lambda: notify_reservation_expired(reservation=reservation)
    )

    if listing_reopened:
        reopened_listing = Listing.objects.get(pk=transaction.listing_id)
        db_transaction.on_commit(
            lambda: notify_waiting_buyers(listing=reopened_listing)
        )

    return reservation


@db_transaction.atomic
def expire_inspection_period(*, inspection):
    inspection = (
        InspectionPeriod.objects
        .select_for_update()
        .select_related(
            "transaction",
            "transaction__buyer",
            "transaction__seller",
            "transaction__listing",
        )
        .get(pk=inspection.pk)
    )

    transaction = (
        Transaction.objects
        .select_for_update()
        .select_related("buyer", "seller", "listing")
        .get(pk=inspection.transaction_id)
    )

    now = timezone.now()

    if inspection.status != InspectionPeriod.Status.ACTIVE:
        raise ValidationError("Inspection hii haipo ACTIVE.")
    if not inspection.expires_at:
        raise ValidationError("Inspection haina muda wa kuisha.")
    if inspection.expires_at > now:
        raise ValidationError("Inspection bado haija-expire.")

    inspection.status = InspectionPeriod.Status.COMPLETED
    inspection.completed_at = now
    inspection.save(update_fields=["status", "completed_at", "updated_at"])

    if transaction.status == Transaction.Status.INSPECTION:
        transaction.status = Transaction.Status.DISPUTED
        transaction.buyer_decision = Transaction.BuyerDecision.PENDING
        transaction.buyer_decision_note = (
            "Inspection imeisha bila buyer decision."
        )
        transaction.buyer_decision_at = now
        transaction.save(update_fields=[
            "status", "buyer_decision", "buyer_decision_note",
            "buyer_decision_at", "updated_at",
        ])

    db_transaction.on_commit(
        lambda: notify_inspection_completed(inspection=inspection)
    )
    return inspection