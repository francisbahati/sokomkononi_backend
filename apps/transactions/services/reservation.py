import logging
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

logger = logging.getLogger(__name__)


RESERVATION_PAYMENT_WINDOW_HOURS = 24  # buyer must pay within 24h
DEFAULT_RESERVATION_HOURS = 48
DEFAULT_INSPECTION_HOURS = 24
ALLOWED_RESERVATION_HOURS = (24, 48, 72)
MAX_INSPECTION_HOURS = 168

# Deprecated: reservations are now charged the flat fee configured by the
# admin in ReservationRate. Kept only so existing imports do not break.
RESERVATION_DEPOSIT_PERCENTAGE = Decimal("10.00")


# ============================================================================
# FEE
# ============================================================================

def get_reservation_fee_config():
    """ReservationRate singleton (pk=1), created on first use."""
    from apps.reservation_rates.models import ReservationRate

    obj, _ = ReservationRate.objects.get_or_create(
        pk=1,
        defaults={
            "flat_fee": Decimal("50000"),
            "days": 3,
            "is_enabled": True,
        },
    )
    return obj


def is_reservation_fee_enabled():
    return get_reservation_fee_config().is_enabled


def calculate_reservation_fee():
    """
    Flat fee decided by the server. 0.00 when the admin disabled the
    reservation fee (reservations are then free).
    """
    config = get_reservation_fee_config()
    if not config.is_enabled:
        return Decimal("0.00")

    fee = Decimal(str(config.flat_fee)).quantize(Decimal("0.01"))
    if fee <= Decimal("0.00"):
        raise ValidationError("Ada ya reservation haijasanidiwa.")
    return fee


def calculate_reservation_deposit(*, agreed_price):
    """Deprecated (percentage deposit). No longer used for charging."""
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


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _lock_reservation(reservation):
    """Lock reservation + its transaction. Call inside an atomic block."""
    reservation = (
        Reservation.objects
        .select_for_update(of=("self",))
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
        .select_for_update(of=("self",))
        .select_related("listing", "buyer", "seller")
        .get(pk=reservation.transaction_id)
    )
    return reservation, transaction


def _activate_reservation(*, reservation, transaction, payment_reference):
    """
    Mark a reservation PAID + ACTIVE and reserve the listing.
    Shared by every payment path (free, credits, FimiPay webhook,
    staff manual). The caller holds the locks and validated the state.
    """
    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )

    if listing.status not in [
        Listing.Status.AVAILABLE,
        Listing.Status.RESERVED,
    ]:
        raise ValidationError(
            "Tangazo hili halipo tena kwenye hali ya "
            "AVAILABLE au RESERVED."
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


# ============================================================================
# CREATE
# ============================================================================

@db_transaction.atomic
def create_reservation(*, transaction, user, duration_hours=DEFAULT_RESERVATION_HOURS):
    transaction = (
        Transaction.objects
        .select_for_update(of=("self",))
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

    # Lock and validate the listing.
    # accept_offer() may have already set it to RESERVED.
    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )
    if listing.status not in [
        Listing.Status.AVAILABLE,
        Listing.Status.RESERVED,
    ]:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya AVAILABLE au RESERVED."
        )

    try:
        duration_hours = int(duration_hours)
    except (TypeError, ValueError):
        raise ValidationError("Muda wa reservation si sahihi.")

    if duration_hours not in ALLOWED_RESERVATION_HOURS:
        raise ValidationError(
            "Reservation inaweza kuwa saa 24, 48 au 72."
        )

    # The amount is decided here, never by the client.
    fee = calculate_reservation_fee()
    now = timezone.now()
    window_end = now + timedelta(hours=RESERVATION_PAYMENT_WINDOW_HOURS)

    existing = (
        Reservation.objects
        .select_for_update(of=("self",))
        .filter(transaction=transaction)
        .first()
    )

    if existing:
        # Buyer retrying after an abandoned / failed payment attempt:
        # reuse the unpaid reservation instead of leaving them stuck.
        if (
            existing.status == Reservation.Status.PENDING_PAYMENT
            and existing.payment_status == Reservation.PaymentStatus.PENDING
        ):
            existing.duration_hours = duration_hours
            existing.deposit_amount = fee
            existing.expires_at = window_end
            existing.save(update_fields=[
                "duration_hours", "deposit_amount", "expires_at",
                "updated_at",
            ])
            reservation = existing
        else:
            raise ValidationError(
                "Reservation tayari ipo kwa Transaction hii."
            )
    else:
        reservation = Reservation.objects.create(
            transaction=transaction,
            deposit_amount=fee,
            duration_hours=duration_hours,
            payment_status=Reservation.PaymentStatus.PENDING,
            status=Reservation.Status.PENDING_PAYMENT,
            # Reservation expires if not paid within the window.
            expires_at=window_end,
        )
        db_transaction.on_commit(
            lambda: notify_reservation_created(reservation=reservation)
        )

    # Fee disabled by admin -> nothing to pay: activate right away.
    if fee == Decimal("0.00"):
        reservation = _activate_reservation(
            reservation=reservation,
            transaction=transaction,
            payment_reference=f"free-{reservation.pk}",
        )

    return reservation


# ============================================================================
# PAYMENT
# ============================================================================

@db_transaction.atomic
def confirm_reservation_payment(*, reservation, payment_reference, user=None):
    """
    Confirm payment WITHOUT FimiPay. Only two cases are allowed:
      - "credits": consume one reservation credit from the buyer.
      - any other reference: staff only (manual confirmation).
    Everything else is paid through FimiPay and confirmed by the webhook,
    never by a reference typed by the client.
    """
    reservation, transaction = _lock_reservation(reservation)

    if reservation.payment_status == Reservation.PaymentStatus.PAID:
        raise ValidationError("Reservation payment tayari imelipwa.")
    if reservation.status != Reservation.Status.PENDING_PAYMENT:
        raise ValidationError(
            "Reservation hii haipo kwenye hatua ya kusubiri malipo."
        )

    payment_reference = (payment_reference or "").strip()
    if not payment_reference:
        raise ValidationError("Payment reference inahitajika.")

    if payment_reference == "credits":
        from apps.credits.services import consume_credit
        # Runs inside this atomic block: if activation fails below, the
        # credit is rolled back instead of being lost.
        if not consume_credit(transaction.buyer, "reservation"):
            raise ValidationError(
                "Hakuna reservation credits za kutosha."
            )
        payment_reference = (
            f"credits-{reservation.pk}-{int(timezone.now().timestamp())}"
        )
    elif not (user is not None and user.is_staff):
        raise ValidationError(
            "Malipo ya reservation yanathibitishwa na mfumo baada ya "
            "kulipa kupitia FimiPay."
        )

    if Reservation.objects.filter(
        payment_reference=payment_reference,
    ).exclude(pk=reservation.pk).exists():
        raise ValidationError(
            "Payment reference hii tayari imetumika."
        )

    return _activate_reservation(
        reservation=reservation,
        transaction=transaction,
        payment_reference=payment_reference,
    )


def initiate_reservation_payment(*, reservation, user, payment_method="mobile", phone=""):
    """Start a FimiPay order for the reservation fee."""
    from apps.payments.fimipay import (
        create_order,
        normalize_payment_method,
    )
    from apps.payments.order_ids import make_order_id

    reservation = (
        Reservation.objects
        .select_related("transaction")
        .get(pk=reservation.pk)
    )

    if user.id != reservation.transaction.buyer_id:
        raise ValidationError("Huruhusiwi kulipia reservation hii.")
    if reservation.payment_status == Reservation.PaymentStatus.PAID:
        raise ValidationError("Reservation payment tayari imelipwa.")
    if reservation.status != Reservation.Status.PENDING_PAYMENT:
        raise ValidationError(
            "Reservation hii haipo kwenye hatua ya kusubiri malipo."
        )

    # Re-price: the admin may have changed (or disabled) the fee since
    # the reservation was created.
    fee = calculate_reservation_fee()
    if fee <= Decimal("0.00"):
        raise ValidationError(
            "Ada ya reservation imezimwa. Hakuna malipo yanayohitajika."
        )
    if reservation.deposit_amount != fee:
        reservation.deposit_amount = fee
        reservation.save(update_fields=["deposit_amount", "updated_at"])

    # Unique per attempt ("RSV-<pk>-<hex>"), parsed by the webhook.
    order_id = make_order_id("RSV", reservation.pk)

    # Network call, deliberately outside any transaction / row lock.
    data = create_order(
        order_id=order_id,
        amount=fee,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=normalize_payment_method(payment_method),
    )

    reservation.payment_reference = data.get("order_id") or order_id
    reservation.save(update_fields=["payment_reference", "updated_at"])
    return data


@db_transaction.atomic
def mark_reservation_paid_from_webhook(*, ref_id, payment_reference):
    """Called by the FimiPay webhook (prefix "RSV"). Idempotent."""
    reservation, transaction = _lock_reservation(
        Reservation.objects.get(pk=ref_id)
    )

    if reservation.payment_status == Reservation.PaymentStatus.PAID:
        return reservation

    if reservation.status != Reservation.Status.PENDING_PAYMENT:
        # Money was received but the reservation can no longer be
        # activated (cancelled / expired). Needs a manual refund.
        raise ValidationError(
            f"Reservation {reservation.pk} imelipwa lakini haipo tena "
            f"kwenye hatua ya kusubiri malipo ({reservation.status})."
        )

    reference = (
        str(payment_reference or "").strip() or reservation.payment_reference
    )
    return _activate_reservation(
        reservation=reservation,
        transaction=transaction,
        payment_reference=reference,
    )


# ============================================================================
# INSPECTION
# ============================================================================

@db_transaction.atomic
def start_inspection_period(*, transaction, user, duration_hours=DEFAULT_INSPECTION_HOURS):
    transaction = (
        Transaction.objects
        .select_for_update(of=("self",))
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

    if duration_hours <= 0 or duration_hours > MAX_INSPECTION_HOURS:
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


# ============================================================================
# EXPIRY
# ============================================================================

@db_transaction.atomic
def expire_reservation(*, reservation):
    reservation = (
        Reservation.objects
        .select_for_update(of=("self",))
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
        .select_for_update(of=("self",))
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
        .select_for_update(of=("self",))
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
        .select_for_update(of=("self",))
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