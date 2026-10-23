# apps/payments/refunds.py
"""
Refund service kwa promotions zilizosimamishwa/kufutwa.

Inatumika na admin_promotions/views.py wakati wa cancel.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Refund

logger = logging.getLogger(__name__)


# ============================================================
# PROMOTION TYPE → USER + AMOUNT
# ============================================================
def _get_promotion_info(obj, type_key):
    """
    Rudisha dict { user, amount_paid, payment_reference } kwa promotion.
    """
    user = None
    amount_paid = Decimal("0.00")
    payment_reference = ""

    # ── Boost ──────────────────────────────────────────────
    if type_key == "boost":
        user = getattr(obj, "seller", None)
        amount_paid = Decimal(str(getattr(obj, "amount", 0) or 0))
        payment_reference = getattr(obj, "payment_reference", "") or ""

    # ── Leading ────────────────────────────────────────────
    elif type_key == "leading":
        user = getattr(obj, "seller", None)
        amount_paid = Decimal(str(getattr(obj, "price", 0) or 0))
        payment_reference = getattr(obj, "payment_reference", "") or ""

    # ── Advertise (BannerAd) ───────────────────────────────
    elif type_key == "advertise":
        user = getattr(obj, "seller", None)
        amount_paid = Decimal(str(getattr(obj, "amount", 0) or 0))
        payment_reference = getattr(obj, "payment_reference", "") or ""

    # ── Reservation ────────────────────────────────────────
    elif type_key == "reservation":
        txn = getattr(obj, "transaction", None)
        user = getattr(txn, "buyer", None) if txn else None
        amount_paid = Decimal(
            str(getattr(obj, "deposit_amount", 0) or 0)
        )
        payment_reference = getattr(obj, "payment_reference", "") or ""

    # ── Reservation extension (ada ya kuongeza muda) ───────
    elif type_key == "extension":
        reservation = getattr(obj, "reservation", None)
        txn = getattr(reservation, "transaction", None) if reservation else None
        user = getattr(txn, "buyer", None) if txn else None
        amount_paid = Decimal(str(getattr(obj, "fee", 0) or 0))
        payment_reference = getattr(obj, "payment_reference", "") or ""

    return {
        "user": user,
        "amount_paid": amount_paid,
        "payment_reference": payment_reference,
    }


# ============================================================
# REFUND PROMOTION
# ============================================================
@transaction.atomic
def refund_promotion(obj, type_key, reason=""):
    """
    Unda refund record kwa promotion iliyofutwa.

    Args:
        obj: promotion instance (ListingBoost, ListingLeading, BannerAd, Reservation)
        type_key: "boost" | "leading" | "advertise" | "reservation"
        reason: sababu ya refund

    Returns:
        Refund instance
    """
    if not obj:
        raise ValidationError("Promotion haipo.")

    info = _get_promotion_info(obj, type_key)

    if not info["user"]:
        raise ValidationError("Mtumiaji wa promotion haipatikani.")

    if info["amount_paid"] <= 0:
        logger.info(
            "refund_promotion: amount_paid = 0 for %s #%s — skipping refund",
            type_key, obj.pk,
        )
        return None

    # ── Angalia kama refund tayari ipo ────────────────────
    existing = Refund.objects.filter(
        promotion_type=type_key.upper(),
        promotion_id=obj.pk,
        status__in=[
            Refund.Status.PENDING,
            Refund.Status.PROCESSING,
            Refund.Status.COMPLETED,
        ],
    ).first()

    if existing:
        logger.info(
            "refund_promotion: refund tayari ipo kwa %s #%s — Refund #%s",
            type_key, obj.pk, existing.pk,
        )
        return existing

    # ── Tengeneza refund ──────────────────────────────────
    refund = Refund.objects.create(
        promotion_type=type_key.upper(),
        promotion_id=obj.pk,
        user=info["user"],
        amount_paid=info["amount_paid"],
        amount_refunded=Decimal("0.00"),
        status=Refund.Status.PENDING,
        method=Refund.Method.MANUAL,
        reason=reason or "",
        payment_reference=info["payment_reference"],
    )

    logger.info(
        "refund_promotion: Refund #%s imeundwa kwa %s #%s (TZS %s)",
        refund.pk, type_key, obj.pk, info["amount_paid"],
    )

    # ── Tuma notification kwa mtumiaji ────────────────────
    _notify_user_refund_pending(refund, obj, type_key)

    return refund


# ============================================================
# MARK REFUND AS COMPLETED
# ============================================================
@transaction.atomic
def mark_refund_completed(refund, processed_by=None, admin_note="", method=None):
    """
    Weka refund kama COMPLETED.
    """
    if not refund:
        raise ValidationError("Refund haipo.")

    if refund.status == Refund.Status.COMPLETED:
        return refund

    refund.status = Refund.Status.COMPLETED
    refund.amount_refunded = refund.amount_paid
    refund.processed_at = timezone.now()
    refund.completed_at = timezone.now()
    refund.processed_by = processed_by
    if admin_note:
        refund.admin_note = admin_note
    if method:
        refund.method = method

    if not refund.refund_reference:
        refund.refund_reference = (
            f"REF-{refund.pk}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        )

    refund.save(update_fields=[
        "status", "amount_refunded", "processed_at", "completed_at",
        "processed_by", "admin_note", "method", "refund_reference",
    ])

    logger.info(
        "mark_refund_completed: Refund #%s imekamilika (TZS %s)",
        refund.pk, refund.amount_refunded,
    )

    _notify_user_refund_completed(refund)

    return refund


# ============================================================
# MARK REFUND AS FAILED
# ============================================================
@transaction.atomic
def mark_refund_failed(refund, admin_note=""):
    """Weka refund kama FAILED."""
    if not refund:
        raise ValidationError("Refund haipo.")

    refund.status = Refund.Status.FAILED
    refund.processed_at = timezone.now()
    if admin_note:
        refund.admin_note = admin_note
    refund.save(update_fields=["status", "processed_at", "admin_note"])

    logger.warning(
        "mark_refund_failed: Refund #%s imeshindwa — %s",
        refund.pk, admin_note,
    )

    return refund


# ============================================================
# NOTIFICATIONS
# ============================================================
def _notify_user_refund_pending(refund, obj, type_key):
    """Tuma notification kwa mtumiaji kuwa refund inasubiri."""
    try:
        from apps.notifications.models import Notification
        from apps.notifications.services.notification import (
            create_notification,
        )

        create_notification(
            recipient=refund.user,
            notification_type=Notification.NotificationType.GENERAL,
            title="Refund Inasubiri",
            message=(
                f"Refund ya TZS {refund.amount_paid:,.0f} kwa "
                f"{type_key} yako inasubiri kushughulikiwa. "
                f"Tutawasiliana nawe hivi karibuni."
            ),
            related_object_type="refunds.Refund",
            related_object_id=refund.pk,
            action_url="/dashboard/transactions",
            priority=Notification.Priority.NORMAL,
        )
    except Exception:
        logger.exception(
            "Failed to notify user about refund #%s", refund.pk,
        )


def _notify_user_refund_completed(refund):
    """Tuma notification kwa mtumiaji kuwa refund imekamilika."""
    try:
        from apps.notifications.models import Notification
        from apps.notifications.services.notification import (
            create_notification,
        )

        create_notification(
            recipient=refund.user,
            notification_type=Notification.NotificationType.GENERAL,
            title="Refund Imekamilika",
            message=(
                f"Refund ya TZS {refund.amount_refunded:,.0f} "
                f"imekamilika. Kumbukumbu: {refund.refund_reference or '—'}"
            ),
            related_object_type="refunds.Refund",
            related_object_id=refund.pk,
            action_url="/dashboard/transactions",
            priority=Notification.Priority.HIGH,
        )
    except Exception:
        logger.exception(
            "Failed to notify user about completed refund #%s", refund.pk,
        )

        # apps/payments/refunds.py

def mark_refund_completed_from_webhook(ref_id, payment_reference=""):
    """
    Inaitwa na FimiPay webhook kama refund imekamilika.
    """
    try:
        refund = Refund.objects.get(pk=ref_id)
    except Refund.DoesNotExist:
        logger.exception("mark_refund_completed_from_webhook: Refund #%s haipo", ref_id)
        return None

    if refund.status == Refund.Status.COMPLETED:
        return refund

    return mark_refund_completed(
        refund,
        method=Refund.Method.FIMIPAY,
        admin_note=f"Auto-completed via FimiPay webhook. Ref: {payment_reference}",
    )