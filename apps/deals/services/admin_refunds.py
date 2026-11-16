# apps/deals/services/admin_refunds.py
"""
Refund kutoka kwenye Deal Room (admin).

Pesa pekee zinazopitia mfumo kwenye deal ni:
  • ada ya reservation (deposit)
  • ada za kuongeza muda wa reservation (extensions)
Malipo ya mwisho yanafanyika NJE ya mfumo, kwa hiyo hayarudishwi hapa.

Ada ya reservation HAIRUDISHWI kiotomatiki (sera ya jukwaa) — admin
anaamua kila mara, kwa sababu iliyoandikwa, na refund inaingia kwenye
ukurasa wa Refunds ("Hazijalipwa") ili ikamilishwe kwa mkono.
"""
from decimal import Decimal

from rest_framework.exceptions import ValidationError

# Refund zilizo hai (zinazuia kuunda nyingine kwa chanzo kimoja)
_ACTIVE_REFUND_STATUSES = ("PENDING", "PROCESSING", "COMPLETED")


def _paid_items(deal_room):
    """Reservation iliyolipwa + extensions zilizolipwa za deal hii."""
    from apps.transactions.models import Reservation, ReservationExtension

    txn = getattr(deal_room, "transaction", None)
    reservation = getattr(txn, "reservation", None) if txn else None
    if not reservation:
        return []

    items = []
    if reservation.payment_status == Reservation.PaymentStatus.PAID:
        items.append({
            "type": "reservation",
            "obj": reservation,
            "amount": Decimal(str(reservation.deposit_amount or 0)),
        })
    for ext in reservation.extensions.filter(
        status=ReservationExtension.Status.PAID,
    ):
        items.append({
            "type": "extension",
            "obj": ext,
            "amount": Decimal(str(ext.fee or 0)),
        })
    return items


def _existing_refund(item):
    from apps.payments.models import Refund

    return (
        Refund.objects
        .filter(
            promotion_type=item["type"].upper(),
            promotion_id=item["obj"].pk,
            status__in=_ACTIVE_REFUND_STATUSES,
        )
        .order_by("-created_at")
        .first()
    )


def refund_overview(deal_room):
    """
    Muhtasari kwa UI: kiasi kinachoweza kurudishwa na hali ya kila kipengele.
    """
    items_out = []
    refundable = Decimal("0.00")
    for item in _paid_items(deal_room):
        existing = _existing_refund(item)
        if existing is None and item["amount"] > 0:
            refundable += item["amount"]
        items_out.append({
            "type": item["type"],
            "id": item["obj"].pk,
            "amount": float(item["amount"]),
            "refund_id": existing.pk if existing else None,
            "refund_status": existing.status if existing else None,
        })
    return {"refundable_amount": float(refundable), "items": items_out}


def refund_deal_payments(*, deal_room, reason):
    """
    Unda Refund (PENDING) kwa kila malipo ya reservation ya deal yenye
    kiasi > 0 ambayo bado hayana refund hai. Rudisha orodha ya Refund
    zilizoundwa.

    Sharti: deal lazima iwe imekwisha (transaction CANCELLED, au
    reservation CANCELLED/EXPIRED) — hatulipi refund mnunuzi akiwa bado
    ameshikilia mali.
    """
    from apps.payments.refunds import refund_promotion
    from apps.transactions.models import Reservation, Transaction

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Sababu ya refund ni lazima.")

    txn = getattr(deal_room, "transaction", None)
    reservation = getattr(txn, "reservation", None) if txn else None
    if not txn or not reservation:
        raise ValidationError("Deal hii haina malipo ya reservation.")

    deal_over = (
        txn.status == Transaction.Status.CANCELLED
        or reservation.status in (
            Reservation.Status.CANCELLED,
            Reservation.Status.EXPIRED,
        )
    )
    if not deal_over:
        raise ValidationError(
            "Ghairi deal (au maliza reservation) kwanza, kisha rudisha malipo."
        )

    pending = [
        i for i in _paid_items(deal_room)
        if i["amount"] > 0 and _existing_refund(i) is None
    ]
    if not pending:
        raise ValidationError(
            "Hakuna malipo yanayoweza kurudishwa (hayakulipwa, au refund "
            "tayari imeundwa)."
        )

    created = []
    for item in pending:
        refund = refund_promotion(
            item["obj"],
            item["type"],
            reason=f"Deal #{deal_room.pk}: {reason}",
        )
        if refund is not None:
            created.append(refund)
    return created
