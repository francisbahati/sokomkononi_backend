import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing
from apps.waiting_list.services.notifications import notify_waiting_buyers

from ..models import (
    InspectionPeriod,
    Reservation,
    ReservationExtension,
    Transaction,
)
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
MAX_INSPECTION_HOURS = 168

# Deprecated: reservations are now charged a per-tier fee configured by
# the admin (see ReservationTier). Kept only so existing imports do not break.
RESERVATION_DEPOSIT_PERCENTAGE = Decimal("10.00")


# ============================================================================
# FEE
# ============================================================================

def get_reservation_settings():
    """ReservationSettings singleton (pk=1), created on first use."""
    from apps.reservation_rates.models import ReservationSettings

    obj, _ = ReservationSettings.objects.get_or_create(pk=1)
    return obj


def is_reservation_fee_enabled():
    return get_reservation_settings().is_enabled


def get_active_reservation_tiers():
    """Tiers zote zilizo hai, zimepangwa."""
    from apps.reservation_rates.models import ReservationTier

    return ReservationTier.objects.filter(is_active=True).order_by(
        "order", "hours",
    )


def get_allowed_reservation_hours():
    """List ya hours zote za tiers zilizo hai."""
    return list(
        get_active_reservation_tiers().values_list("hours", flat=True)
    )


def calculate_reservation_fee(duration_hours):
    """
    Fee ya tier fulani. 0.00 kama admin amezima reservation fee
    (kwa hiyo reservations ni bure).

    Inarusha ValidationError kama tier ya hours hiyo haipo / haipo hai.
    """
    from apps.reservation_rates.models import ReservationTier

    settings = get_reservation_settings()
    if not settings.is_enabled:
        return Decimal("0.00")

    try:
        hours = int(duration_hours)
    except (TypeError, ValueError):
        raise ValidationError("Muda wa reservation si sahihi.")

    try:
        tier = ReservationTier.objects.get(hours=hours, is_active=True)
    except ReservationTier.DoesNotExist:
        raise ValidationError(
            f"Hakuna tier ya reservation kwa saa {hours}. "
            f"Chagua muda uliopo kwenye orodha."
        )

    fee = Decimal(str(tier.fee)).quantize(Decimal("0.01"))
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


def _restore_deal_room(transaction):
    """
    Reservation imeisha / imeondolewa -> Deal Room irudi ACCEPTED ili
    mnunuzi aweze kureserve tena (bei bado imekubaliwa).
    """
    from apps.deals.models import DealRoom

    deal_room = (
        DealRoom.objects
        .select_for_update()
        .filter(pk=transaction.deal_room_id)
        .first()
    )
    if deal_room and deal_room.status == DealRoom.Status.RESERVED:
        deal_room.status = DealRoom.Status.ACCEPTED
        deal_room.save(update_fields=["status", "updated_at"])
        return True
    return False


def restore_waiting_list_entry(*, reservation):
    """
    Mnunuzi aliyechukua nafasi kupitia waiting list (claim) lakini
    hakulipa, anarudishwa kwenye foleni (mwisho wa foleni, ili anayefuata
    apate nafasi kwanza). Haiguswi entry za zamani zisizohusiana.

    Itumike ndani ya atomic block. Inarudisha entry au None.
    """
    from django.db.models import Max
    from apps.waiting_list.models import WaitingListEntry

    transaction = reservation.transaction

    entry = (
        WaitingListEntry.objects
        .select_for_update()
        .filter(
            listing_id=transaction.listing_id,
            buyer_id=transaction.buyer_id,
            status=WaitingListEntry.Status.FULFILLED,
            updated_at__gte=reservation.created_at,
        )
        .order_by("-updated_at")
        .first()
    )
    if not entry:
        return None

    active = [
        WaitingListEntry.Status.WAITING,
        WaitingListEntry.Status.NOTIFIED,
    ]
    if WaitingListEntry.objects.filter(
        listing_id=transaction.listing_id,
        buyer_id=transaction.buyer_id,
        status__in=active,
    ).exists():
        return None

    last = (
        WaitingListEntry.objects
        .filter(listing_id=transaction.listing_id, status__in=active)
        .aggregate(m=Max("position"))["m"]
        or 0
    )
    entry.status = WaitingListEntry.Status.WAITING
    entry.position = last + 1
    entry.notified_at = None
    entry.respond_by = None
    entry.save(update_fields=[
        "status", "position", "notified_at", "respond_by", "updated_at",
    ])
    return entry


def _activate_reservation(*, reservation, transaction, payment_reference):
    """
    Mark a reservation PAID + ACTIVE and reserve the listing.
    Shared by every payment path (free, credits, FimiPay webhook,
    staff manual). The caller holds the locks and validated the state.

    Pia:
      - Inabadilisha DealRoom.status → RESERVED
      - Inaunda InspectionPeriod papo hapo (status: ACTIVE)
      - Inabadilisha Transaction.status → INSPECTION
      - Inatuma notifications (RESERVATION_PAID + INSPECTION_STARTED)
    """
    from apps.deals.models import DealRoom
    from ..models import InspectionPeriod   # ⬅️ ONGEZA

    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )

    if listing.status not in [
        Listing.Status.LIVE,
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

    # ── MPYA: Badilisha DealRoom.status kuwa RESERVED ──
    try:
        deal_room = DealRoom.objects.select_for_update().get(
            pk=transaction.deal_room_id,
        )
        if deal_room.status == DealRoom.Status.ACCEPTED:
            deal_room.status = DealRoom.Status.RESERVED
            deal_room.save(update_fields=["status", "updated_at"])
    except DealRoom.DoesNotExist:
        pass

    # ── Inspection ina muda SAWA na reservation ──
    # (inaisha wakati mmoja na reservation; extend inaiongeza pia)
    try:
        inspection = (
            InspectionPeriod.objects
            .select_for_update()
            .filter(transaction=transaction)
            .first()
        )
        started = None
        if inspection is None:
            started = InspectionPeriod.objects.create(
                transaction=transaction,
                duration_hours=reservation.duration_hours,
                starts_at=now,
                expires_at=expires_at,
                status=InspectionPeriod.Status.ACTIVE,
            )
        elif inspection.status == InspectionPeriod.Status.CANCELLED:
            # Reservation mpya baada ya kuondoa / kuisha: tumia tena
            inspection.duration_hours = reservation.duration_hours
            inspection.starts_at = now
            inspection.expires_at = expires_at
            inspection.status = InspectionPeriod.Status.ACTIVE
            inspection.completed_at = None
            inspection.save(update_fields=[
                "duration_hours", "starts_at", "expires_at",
                "status", "completed_at", "updated_at",
            ])
            started = inspection

        if started is not None:
            transaction.status = Transaction.Status.INSPECTION
            transaction.save(update_fields=["status", "updated_at"])
            db_transaction.on_commit(
                lambda: notify_inspection_started(inspection=started)
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to create inspection for transaction %s",
            transaction.pk,
        )

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
    # Kureserve tena: reservation ya awali iliondolewa / iliisha, Deal Room
    # imerejeshwa ACCEPTED, na transaction ni CANCELLED.
    reset_mode = False
    if transaction.status == Transaction.Status.CANCELLED:
        from apps.deals.models import DealRoom

        deal_room = (
            DealRoom.objects
            .select_for_update()
            .get(pk=transaction.deal_room_id)
        )
        previous = (
            Reservation.objects
            .select_for_update(of=("self",))
            .filter(transaction=transaction)
            .first()
        )
        if (
            deal_room.status == DealRoom.Status.ACCEPTED
            and previous
            and previous.status in (
                Reservation.Status.CANCELLED,
                Reservation.Status.EXPIRED,
            )
        ):
            reset_mode = True

    if not reset_mode and (
        transaction.status != Transaction.Status.RESERVATION_PENDING
    ):
        raise ValidationError(
            "Transaction hii haipo tayari kwa reservation."
        )

    # Lock and validate the listing.
    # accept_offer() may have already set it to RESERVED.
    listing = Listing.objects.select_for_update().get(
        pk=transaction.listing_id,
    )
    if listing.status not in [
        Listing.Status.LIVE,
        Listing.Status.RESERVED,
    ]:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya AVAILABLE au RESERVED."
        )

    if reset_mode and listing.status != Listing.Status.LIVE:
        raise ValidationError(
            "Tangazo hili limechukuliwa na mtu mwingine. "
            "Huwezi kureserve tena."
        )

    try:
        duration_hours = int(duration_hours)
    except (TypeError, ValueError):
        raise ValidationError("Muda wa reservation si sahihi.")

    # Validate against active tiers (dynamic, admin-controlled).
    allowed = get_allowed_reservation_hours()
    if not allowed:
        raise ValidationError(
            "Hakuna tiers za reservation zilizo hai. "
            "Wasiliana na admin."
        )
    if duration_hours not in allowed:
        hours_str = ", ".join(str(h) for h in sorted(allowed))
        raise ValidationError(
            f"Reservation inaweza kuwa saa: {hours_str}."
        )

    # The amount is decided here, never by the client.
    # Fee depends on the tier (duration_hours).
    fee = calculate_reservation_fee(duration_hours)
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
        elif reset_mode:
            existing.status = Reservation.Status.PENDING_PAYMENT
            existing.payment_status = Reservation.PaymentStatus.PENDING
            existing.payment_reference = None
            existing.paid_at = None
            existing.starts_at = None
            existing.refund_reference = ""
            existing.refunded_at = None
            existing.duration_hours = duration_hours
            existing.deposit_amount = fee
            existing.expires_at = window_end
            existing.save(update_fields=[
                "status", "payment_status", "payment_reference", "paid_at",
                "starts_at", "refund_reference", "refunded_at",
                "duration_hours", "deposit_amount", "expires_at",
                "updated_at",
            ])
            transaction.status = Transaction.Status.RESERVATION_PENDING
            transaction.cancelled_at = None
            transaction.cancellation_reason = ""
            transaction.save(update_fields=[
                "status", "cancelled_at", "cancellation_reason",
                "updated_at",
            ])
            reservation = existing
            db_transaction.on_commit(
                lambda: notify_reservation_created(reservation=reservation)
            )
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
        if user is None or user.id != transaction.buyer_id:
            raise ValidationError("Ni mnunuzi pekee anayeweza kutumia credits.")
        from apps.credits.services import consume_credit
        if not consume_credit(user=transaction.buyer, service_key="reservation"):
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

    # Use the STORED amount — do NOT re-price (avoids orphaned FimiPay orders).
    fee = reservation.deposit_amount
    if fee <= Decimal("0.00"):
        raise ValidationError(
            "Ada ya reservation si sahihi. Wasiliana na admin."
        )

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
        # activated. Record the payment, flag for refund, alert admins.
        reservation.payment_status = Reservation.PaymentStatus.PAID
        reservation.payment_reference = (
            str(payment_reference or "").strip()
            or reservation.payment_reference
        )
        reservation.paid_at = timezone.now()
        reservation.save(update_fields=[
            "payment_status", "payment_reference", "paid_at", "updated_at",
        ])

        import logging as _l
        _l.getLogger(__name__).error(
            "REFUND REQUIRED: reservation %s paid but status=%s",
            reservation.pk, reservation.status,
        )
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services.notification import (
                create_notification_for_admins,
            )
            create_notification_for_admins(
                notification_type=Notification.NotificationType.GENERAL,
                title="Refund inahitajika — Reservation imelipwa baada ya kuisha",
                message=(
                    f"Reservation #{reservation.pk} ililipwa na mteja "
                    f"lakini ilikuwa imeisha / imefungwa. "
                    f"Tafadhali fanya refund manually."
                ),
                priority=Notification.Priority.URGENT,
                related_object_type="Reservation",
                related_object_id=reservation.pk,
                action_url="",
            )
        except Exception:
            pass
        return reservation

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
            listing.status = Listing.Status.LIVE
            listing.save(update_fields=["status", "updated_at"])
            listing_reopened = True

        _restore_deal_room(transaction)

    inspection = getattr(transaction, "inspection_period", None)
    if inspection and (
        inspection.status in [
            InspectionPeriod.Status.PENDING, InspectionPeriod.Status.ACTIVE,
        ]
        or (
            # Imekamilika pamoja na reservation (angalia expire_inspection)
            inspection.status == InspectionPeriod.Status.COMPLETED
            and transaction.status == Transaction.Status.CANCELLED
        )
    ):
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

    # Inspection na reservation huisha pamoja. Kama reservation pia imefika
    # mwisho, acha expire_reservation ifunge transaction na kurudisha mali
    # sokoni (isiingie DISPUTED).
    reservation_ending = False
    linked = getattr(transaction, "reservation", None)
    if (
        linked is not None
        and linked.status == Reservation.Status.ACTIVE
        and linked.expires_at
        and linked.expires_at <= now
    ):
        reservation_ending = True

    if (
        transaction.status == Transaction.Status.INSPECTION
        and not reservation_ending
    ):
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


@db_transaction.atomic
def mark_reservation_as_refunded(*, ref_id, reason=""):
    reservation = Reservation.objects.select_for_update().get(pk=ref_id)
    if reservation.payment_status == Reservation.PaymentStatus.REFUNDED:
        return reservation
    reservation.payment_status = Reservation.PaymentStatus.REFUNDED
    reservation.refunded_at = timezone.now()
    reservation.refund_reference = reason or ""
    reservation.save(update_fields=[
        "payment_status", "refunded_at", "refund_reference", "updated_at",
    ])
    return reservation


# ============================================================================
# REMOVE RESERVATION BY BUYER (njia B)
# ============================================================================
# Tofauti na expire_reservation, function hii HAIANGALII expires_at.
# Buyer anaweza kuondoa reservation yake wakati wowote kabla ya
# transaction kukamilika. Reservation Fee HAIRUDISHWI.

@db_transaction.atomic
def remove_reservation_by_buyer(*, reservation):
    """
    Buyer anaondoa reservation yake (hiari, muda wowote).
    - reservation.status       → CANCELLED
    - transaction.status       → CANCELLED
    - listing.status           → LIVE (kama ilikuwa RESERVED)
    - inspection_period.status → CANCELLED (kama ipo)
    - Waiting list inaarifiwa  (kama listing ilirudi LIVE)

    Reservation Fee HAIRUDISHWI.
    """
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

    if reservation.status not in [
        Reservation.Status.ACTIVE,
        Reservation.Status.PENDING_PAYMENT,
    ]:
        raise ValidationError(
            "Reservation hii haiwezi kuondolewa kwa hali yake ya sasa "
            f"({reservation.status})."
        )

    was_unpaid = reservation.status == Reservation.Status.PENDING_PAYMENT

    if transaction.status in [
        Transaction.Status.COMPLETED,
        Transaction.Status.CANCELLED,
    ]:
        raise ValidationError(
            "Transaction hii haiwezi kughairiwa tena."
        )

    now = timezone.now()

    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])

    listing_reopened = False

    if transaction.status in [
        Transaction.Status.RESERVED,
        Transaction.Status.INSPECTION,
        Transaction.Status.READY_FOR_FINAL_PAYMENT,
        Transaction.Status.RESERVATION_PENDING,
    ]:
        transaction.status = Transaction.Status.CANCELLED
        transaction.cancelled_at = now
        transaction.cancellation_reason = (
            "Mnunuzi ameondoa reservation."
        )
        transaction.save(update_fields=[
            "status", "cancelled_at", "cancellation_reason", "updated_at",
        ])

        listing = Listing.objects.select_for_update().get(
            pk=transaction.listing_id,
        )
        if listing.status == Listing.Status.RESERVED:
            listing.status = Listing.Status.LIVE
            listing.save(update_fields=["status", "updated_at"])
            listing_reopened = True

        # Deal Room irejeshwe ili mnunuzi aweze kureserve tena
        _restore_deal_room(transaction)

    inspection = getattr(transaction, "inspection_period", None)
    if inspection and inspection.status in [
        InspectionPeriod.Status.PENDING,
        InspectionPeriod.Status.ACTIVE,
    ]:
        inspection.status = InspectionPeriod.Status.CANCELLED
        inspection.save(update_fields=["status", "updated_at"])

    # Alichukua nafasi kupitia waiting list lakini hakulipa -> arudi foleni
    waiting_restored = False
    if was_unpaid:
        waiting_restored = (
            restore_waiting_list_entry(reservation=reservation) is not None
        )

    db_transaction.on_commit(
        lambda: notify_reservation_expired(reservation=reservation)
    )

    if waiting_restored and not listing_reopened:
        listing_reopened = True

    if listing_reopened:
        reopened_listing = Listing.objects.get(pk=transaction.listing_id)
        db_transaction.on_commit(
            lambda: notify_waiting_buyers(listing=reopened_listing)
        )

    return reservation

# ============================================================================
# EXTEND RESERVATION (lazima ilipwe kwanza)
# ============================================================================

def _apply_extension(*, extension, reservation, transaction, payment_reference):
    """
    Ongeza muda wa reservation NA inspection baada ya malipo kuthibitishwa.
    Caller ameshika locks. Idempotent.
    """
    if extension.status == ReservationExtension.Status.PAID:
        return reservation

    now = timezone.now()

    if reservation.status != Reservation.Status.ACTIVE:
        # Pesa imepokelewa lakini reservation haipo ACTIVE tena -> refund
        extension.status = ReservationExtension.Status.PAID
        extension.payment_reference = (
            str(payment_reference or "").strip() or extension.payment_reference
        )
        extension.paid_at = now
        extension.save(update_fields=[
            "status", "payment_reference", "paid_at", "updated_at",
        ])
        logger.error(
            "REFUND REQUIRED: extension %s paid but reservation %s status=%s",
            extension.pk, reservation.pk, reservation.status,
        )
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services.notification import (
                create_notification_for_admins,
            )
            create_notification_for_admins(
                notification_type=Notification.NotificationType.GENERAL,
                title="Refund inahitajika — Extension imelipwa baada ya reservation kuisha",
                message=(
                    f"Extension #{extension.pk} ya Reservation "
                    f"#{reservation.pk} ililipwa lakini reservation "
                    f"haipo ACTIVE. Tafadhali fanya refund manually."
                ),
                priority=Notification.Priority.URGENT,
                related_object_type="Reservation",
                related_object_id=reservation.pk,
                action_url="",
            )
        except Exception:
            logger.exception("extension refund alert failed")
        return reservation

    base = max(reservation.expires_at or now, now)
    hours = extension.additional_hours

    reservation.duration_hours += hours
    reservation.expires_at = base + timedelta(hours=hours)
    reservation.deposit_amount = reservation.deposit_amount + extension.fee
    reservation.save(update_fields=[
        "duration_hours", "expires_at", "deposit_amount", "updated_at",
    ])

    # Inspection iende sambamba na reservation
    inspection = (
        InspectionPeriod.objects
        .select_for_update()
        .filter(
            transaction=transaction,
            status=InspectionPeriod.Status.ACTIVE,
        )
        .first()
    )
    if inspection:
        inspection.duration_hours += hours
        inspection.expires_at = reservation.expires_at
        inspection.save(update_fields=[
            "duration_hours", "expires_at", "updated_at",
        ])

    extension.status = ReservationExtension.Status.PAID
    extension.payment_reference = (
        str(payment_reference or "").strip() or extension.payment_reference
    )
    extension.paid_at = now
    extension.save(update_fields=[
        "status", "payment_reference", "paid_at", "updated_at",
    ])

    def _notify():
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services.notification import (
                create_notification,
            )
            for recipient in (transaction.buyer, transaction.seller):
                create_notification(
                    recipient=recipient,
                    notification_type=Notification.NotificationType.GENERAL,
                    title="Reservation imeongezwa muda",
                    message=(
                        f"Reservation ya Transaction #{transaction.id} "
                        f"imeongezwa saa {hours}. "
                        f"Inaisha: {reservation.expires_at}."
                    ),
                    priority=Notification.Priority.HIGH,
                    related_object_type="Reservation",
                    related_object_id=reservation.id,
                    action_url=f"/transactions/{transaction.id}",
                )
        except Exception:
            logger.exception("reservation extend notify failed")

    db_transaction.on_commit(_notify)
    return reservation


@db_transaction.atomic
def request_reservation_extension(*, reservation, user, additional_hours):
    """
    Unda ombi la extension (PENDING_PAYMENT). Muda lazima uwe tier hai.
    Ada = ada ya tier hiyo. Kama admin amezima ada (0.00) -> inaongezwa
    papo hapo bila malipo.
    """
    reservation, transaction = _lock_reservation(reservation)

    if user is None or user.id != transaction.buyer_id:
        raise ValidationError(
            "Ni mnunuzi pekee anayeweza kuongeza muda wa reservation."
        )
    if reservation.status != Reservation.Status.ACTIVE:
        raise ValidationError(
            "Reservation haipo ACTIVE. Haiwezi kuongezwa muda."
        )

    try:
        additional_hours = int(additional_hours)
    except (TypeError, ValueError):
        raise ValidationError("additional_hours inahitajika (integer).")

    allowed = get_allowed_reservation_hours()
    if not allowed:
        raise ValidationError("Hakuna tiers za reservation zilizo hai.")
    if additional_hours not in allowed:
        hours_str = ", ".join(str(h) for h in sorted(allowed))
        raise ValidationError(
            f"Muda wa kuongeza lazima uwe mmoja wa: {hours_str}."
        )

    fee = calculate_reservation_fee(additional_hours)

    # Maombi ya zamani ambayo hayakulipwa yanafungwa
    ReservationExtension.objects.filter(
        reservation=reservation,
        status=ReservationExtension.Status.PENDING_PAYMENT,
    ).update(status=ReservationExtension.Status.CANCELLED)

    extension = ReservationExtension.objects.create(
        reservation=reservation,
        additional_hours=additional_hours,
        fee=fee,
    )

    if fee == Decimal("0.00"):
        _apply_extension(
            extension=extension,
            reservation=reservation,
            transaction=transaction,
            payment_reference=f"free-ext-{extension.pk}",
        )
    return extension


@db_transaction.atomic
def confirm_extension_with_credits(*, extension, user):
    """Lipia extension kwa reservation credit (huu ndio njia isiyo FimiPay)."""
    extension = (
        ReservationExtension.objects
        .select_for_update(of=("self",))
        .get(pk=extension.pk)
    )
    reservation, transaction = _lock_reservation(extension.reservation)

    if extension.status != ReservationExtension.Status.PENDING_PAYMENT:
        raise ValidationError("Extension hii haipo kwenye hatua ya malipo.")
    if user is None or user.id != transaction.buyer_id:
        raise ValidationError("Ni mnunuzi pekee anayeweza kutumia credits.")

    from apps.credits.services import consume_credit
    if not consume_credit(user=transaction.buyer, service_key="reservation"):
        raise ValidationError("Hakuna reservation credits za kutosha.")

    return _apply_extension(
        extension=extension,
        reservation=reservation,
        transaction=transaction,
        payment_reference=f"credits-ext-{extension.pk}-{int(timezone.now().timestamp())}",
    )


def initiate_extension_payment(*, extension, user, payment_method="mobile", phone=""):
    """Anzisha FimiPay order ya ada ya extension (prefix "RSX")."""
    from apps.payments.fimipay import (
        create_order,
        normalize_payment_method,
    )
    from apps.payments.order_ids import make_order_id

    extension = (
        ReservationExtension.objects
        .select_related("reservation__transaction")
        .get(pk=extension.pk)
    )
    transaction = extension.reservation.transaction

    if user.id != transaction.buyer_id:
        raise ValidationError("Huruhusiwi kulipia extension hii.")
    if extension.status != ReservationExtension.Status.PENDING_PAYMENT:
        raise ValidationError("Extension hii haipo kwenye hatua ya malipo.")
    if extension.fee <= Decimal("0.00"):
        raise ValidationError("Ada ya extension si sahihi.")

    order_id = make_order_id("RSX", extension.pk)

    data = create_order(
        order_id=order_id,
        amount=extension.fee,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=normalize_payment_method(payment_method),
    )

    extension.payment_reference = data.get("order_id") or order_id
    extension.save(update_fields=["payment_reference", "updated_at"])
    return data


@db_transaction.atomic
def mark_extension_paid_from_webhook(*, ref_id, payment_reference):
    """FimiPay webhook (prefix "RSX"). Idempotent."""
    extension = (
        ReservationExtension.objects
        .select_for_update(of=("self",))
        .get(pk=ref_id)
    )
    if extension.status == ReservationExtension.Status.PAID:
        return extension.reservation

    reservation, transaction = _lock_reservation(extension.reservation)
    return _apply_extension(
        extension=extension,
        reservation=reservation,
        transaction=transaction,
        payment_reference=payment_reference,
    )


@db_transaction.atomic
def mark_extension_as_refunded(*, ref_id, reason=""):
    """
    FimiPay refund webhook (prefix "RSX"). Idempotent.

    Muda uliokwisha ongezwa HAUONDOLEWI kiotomatiki (inaweza kufunga
    reservation ya mnunuzi ghafla). Admin anaarifiwa akague.
    """
    extension = (
        ReservationExtension.objects
        .select_for_update(of=("self",))
        .select_related("reservation__transaction")
        .get(pk=ref_id)
    )
    if extension.status == ReservationExtension.Status.REFUNDED:
        return extension

    was_applied = extension.status == ReservationExtension.Status.PAID

    extension.status = ReservationExtension.Status.REFUNDED
    extension.refunded_at = timezone.now()
    extension.refund_reference = reason or ""
    extension.save(update_fields=[
        "status", "refunded_at", "refund_reference", "updated_at",
    ])

    if was_applied:
        try:
            from apps.notifications.models import Notification
            from apps.notifications.services.notification import (
                create_notification_for_admins,
            )
            create_notification_for_admins(
                notification_type=Notification.NotificationType.GENERAL,
                title="Extension imerefundiwa — kagua muda wa reservation",
                message=(
                    f"Extension #{extension.pk} (+{extension.additional_hours}h) "
                    f"ya Reservation #{extension.reservation_id} "
                    f"imerefundiwa, lakini muda ulioongezwa haukuondolewa. "
                    f"Kagua kama inahitajika."
                ),
                priority=Notification.Priority.HIGH,
                related_object_type="Reservation",
                related_object_id=extension.reservation_id,
                action_url="",
            )
        except Exception:
            logger.exception("extension refund admin notify failed")

    return extension