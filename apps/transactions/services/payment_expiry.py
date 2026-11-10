# apps/transactions/services/payment_expiry.py
"""
Kazi ya mara kwa mara (cron kila dakika 5, au celery beat):

1. Mnunuzi hakulipa ndani ya saa 72 (hakuna uthibitisho) => deal inaghairiwa,
   mali inarudi sokoni.
2. Muuzaji hakujibu ndani ya saa 1 baada ya uthibitisho => rufaa kwa admin.
   (Haikamilishwi yenyewe kwa sababu malipo hayajathibitishwa.)
"""
import logging

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.deals.services.system_messages import post_system_message

from ..models import Transaction
from . import payment_rules as rules
from .transaction import cancel_transaction

logger = logging.getLogger(__name__)


def _cancel_unpaid(tx_id, now):
    with db_transaction.atomic():
        tx = (
            Transaction.objects.select_for_update(of=("self",))
            .select_related("buyer")
            .get(pk=tx_id)
        )
        # Rudia ukaguzi ndani ya lock (huenda hali imebadilika)
        if (
            tx.status != Transaction.Status.READY_FOR_FINAL_PAYMENT
            or tx.final_payment_uploaded_at
            or not tx.final_payment_due_at
            or tx.final_payment_due_at > now
        ):
            return False
        post_system_message(
            deal_room_id=tx.deal_room_id,
            code="PAYMENT_WINDOW_EXPIRED",
            actor=tx.buyer,
            data={"window_hours": rules.FINAL_PAYMENT_WINDOW_HOURS,
                  "key": f"expired-{tx.pk}"},
        )
        cancel_transaction(
            transaction=tx,
            user=tx.buyer,
            reason=(
                "Muda wa kulipa umeisha "
                f"(saa {rules.FINAL_PAYMENT_WINDOW_HOURS})."
            ),
        )
        return True


def _escalate_silent_seller(tx_id, now):
    with db_transaction.atomic():
        tx = (
            Transaction.objects.select_for_update(of=("self",))
            .select_related("seller")
            .get(pk=tx_id)
        )
        if (
            tx.status != Transaction.Status.READY_FOR_FINAL_PAYMENT
            or not tx.final_payment_uploaded_at
            or not tx.seller_response_due_at
            or tx.seller_response_due_at > now
        ):
            return False
        tx.status = Transaction.Status.DISPUTED
        tx.dispute_reason = rules.DISPUTE_SELLER_NO_RESPONSE
        tx.seller_response_due_at = None
        tx.save(update_fields=[
            "status", "dispute_reason", "seller_response_due_at", "updated_at",
        ])
        post_system_message(
            deal_room_id=tx.deal_room_id,
            code="APPEAL_OPENED",
            actor=tx.seller,
            data={"reason": rules.DISPUTE_SELLER_NO_RESPONSE,
                  "key": f"silent-{tx.pk}-{tx.proof_attempts}"},
        )
        return True


def expire_overdue_payments(now=None):
    now = now or timezone.now()
    cancelled = escalated = 0

    unpaid_ids = list(
        Transaction.objects.filter(
            status=Transaction.Status.READY_FOR_FINAL_PAYMENT,
            final_payment_uploaded_at__isnull=True,
            final_payment_due_at__lt=now,
        ).values_list("pk", flat=True)
    )
    for pk in unpaid_ids:
        try:
            cancelled += int(_cancel_unpaid(pk, now))
        except Exception:
            logger.exception("auto-cancel failed tx=%s", pk)

    silent_ids = list(
        Transaction.objects.filter(
            status=Transaction.Status.READY_FOR_FINAL_PAYMENT,
            final_payment_uploaded_at__isnull=False,
            seller_response_due_at__lt=now,
        ).values_list("pk", flat=True)
    )
    for pk in silent_ids:
        try:
            escalated += int(_escalate_silent_seller(pk, now))
        except Exception:
            logger.exception("escalate failed tx=%s", pk)

    return {"cancelled": cancelled, "escalated": escalated}
