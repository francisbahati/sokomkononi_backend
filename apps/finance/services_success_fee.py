# apps/finance/services_success_fee.py
"""
Success fee payment logic (transactions report download).

Flow:
  1. POST /success-fee/  -> create_success_fee_payment() + initiate_...()
  2. FimiPay webhook (prefix "SFE") -> mark_success_fee_paid_from_webhook()
  3. GET  /success-fee/download/ -> has_valid_success_fee_payment()

The amount is always computed here on the server; the client never
chooses what it pays.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.payments.fimipay import (
    create_order,
    get_order_status,
    normalize_payment_method,
)
from apps.payments.order_ids import make_order_id

from .models import SuccessFeePayment

logger = logging.getLogger(__name__)

ORDER_PREFIX = "SFE"
DEFAULT_PURPOSE = "download"

# A paid fee unlocks downloads (any format) for this long.
DOWNLOAD_VALID_HOURS = 24


def compute_download_fee(config):
    """
    Fee shown by /success-fee/status/ is config.min_fee, so that is what
    is charged. (config.percentage / max_fee are not applied to report
    downloads.)
    """
    fee = Decimal(str(config.min_fee))
    if fee <= Decimal("0"):
        raise ValidationError({"detail": "Ada ya mafanikio haijasanidiwa."})
    return fee


def create_success_fee_payment(*, user, purpose, amount):
    return SuccessFeePayment.objects.create(
        user=user,
        purpose=(purpose or DEFAULT_PURPOSE)[:50],
        amount=amount,
        payment_status=SuccessFeePayment.PaymentStatus.PENDING,
    )


def initiate_success_fee_payment(*, payment, user, payment_method="mobile", phone=""):
    if payment.user_id != user.id:
        raise ValidationError({"detail": "Huruhusiwi kulipia ada hii."})
    if payment.payment_status == SuccessFeePayment.PaymentStatus.PAID:
        raise ValidationError({"detail": "Ada hii tayari imelipiwa."})

    # Unique per attempt ("SFE-<pk>-<hex>"), parsed by the webhook.
    order_id = make_order_id(ORDER_PREFIX, payment.pk)

    # Network call is deliberately outside any transaction/row lock.
    data = create_order(
        order_id=order_id,
        amount=payment.amount,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=normalize_payment_method(payment_method),
    )

    payment.payment_reference = data.get("order_id") or order_id
    payment.save(update_fields=["payment_reference", "updated_at"])
    return data


@transaction.atomic
def mark_success_fee_paid(*, payment_id, payment_reference):
    payment = SuccessFeePayment.objects.select_for_update().get(pk=payment_id)

    # Idempotent: webhook retries and the status-check fallback can race.
    if payment.payment_status == SuccessFeePayment.PaymentStatus.PAID:
        return payment

    reference = (str(payment_reference or "").strip()) or payment.payment_reference
    if (
        reference
        and reference != payment.payment_reference
        and SuccessFeePayment.objects
        .filter(payment_reference=reference).exclude(pk=payment.pk).exists()
    ):
        reference = payment.payment_reference  # keep ours; unique column

    payment.payment_status = SuccessFeePayment.PaymentStatus.PAID
    payment.payment_reference = reference
    payment.paid_at = timezone.now()
    payment.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])
    return payment


def mark_success_fee_paid_from_webhook(*, ref_id, payment_reference):
    return mark_success_fee_paid(
        payment_id=ref_id, payment_reference=payment_reference,
    )


def has_valid_success_fee_payment(user):
    """True if the user has paid the success fee recently."""
    since = timezone.now() - timedelta(hours=DOWNLOAD_VALID_HOURS)

    if SuccessFeePayment.objects.filter(
        user=user,
        payment_status=SuccessFeePayment.PaymentStatus.PAID,
        paid_at__gte=since,
    ).exists():
        return True

    # The webhook may not have arrived yet (the frontend often sees
    # SUCCESS first). Ask FimiPay directly - this is server-to-server,
    # so it cannot be forged by the client.
    pending = (
        SuccessFeePayment.objects
        .filter(
            user=user,
            payment_status=SuccessFeePayment.PaymentStatus.PENDING,
            created_at__gte=since,
        )
        .exclude(payment_reference__isnull=True)
        .exclude(payment_reference="")
        .order_by("-created_at")[:3]
    )
    for payment in pending:
        try:
            data = get_order_status(payment.payment_reference)
        except ValidationError:
            continue
        if str(data.get("payment_status") or "").upper() == "SUCCESS":
            mark_success_fee_paid(
                payment_id=payment.pk,
                payment_reference=data.get("transid") or payment.payment_reference,
            )
            return True

    return False