"""
Background sync of FimiPay state.

  - refresh_pending_payouts: poll FimiPay for any PENDING / PROCESSING
    payout and update its stored status. Runs every 10 minutes.
"""
import logging

from celery import shared_task

from .fimipay import get_payout_status
from .models import Payout

logger = logging.getLogger(__name__)


@shared_task(name="payments.refresh_pending_payouts")
def refresh_pending_payouts():
    from .api import _apply_status

    pending = Payout.objects.filter(
        status__in=[Payout.Status.PENDING, Payout.Status.PROCESSING],
        withdrawal_id__isnull=False,
    )

    updated = 0
    failed = 0
    for payout in pending:
        try:
            data = get_payout_status(payout.withdrawal_id)
            _apply_status(payout, data)
            updated += 1
        except Exception:
            failed += 1
            logger.exception(
                "Failed to sync payout %s (withdrawal %s)",
                payout.pk, payout.withdrawal_id,
            )

    logger.info(
        "refresh_pending_payouts: updated=%s failed=%s",
        updated, failed,
    )
    return {"updated": updated, "failed": failed}
