# apps/payments/tasks.py
"""
Background sync of FimiPay state.

  - refresh_pending_payouts: poll FimiPay for any PENDING / PROCESSING
    payout and update its stored status. Runs every 10 minutes.

  - sync_pending_fimipay_statuses: poll FimiPay for any PENDING order
    (ListingFee, ListingBoost, BundlePurchase, BannerAd, SuccessFeePayment,
    ListingLeading) and update statuses. Runs every 5 minutes.
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


# ============================================================
# FimiPay status sync — orders (ListingFee, Boost, Bundle, etc.)
# ============================================================
@shared_task(
    name="payments.sync_pending_fimipay_statuses",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_pending_fimipay_statuses(self, since_hours=720):
    """
    Sync FimiPay orders zote PENDING.

    Inaitwa na Celery Beat kila dakika 5.
    """
    from apps.payments.services.status_sync import sync_all_pending

    try:
        result = sync_all_pending(since_hours=since_hours)
        logger.info(
            f"[celery] fimipay sync: "
            f"checked={result['total_checked']} "
            f"updated={result['total_updated']}"
        )
        return result
    except Exception as exc:
        logger.exception("[celery] fimipay sync failed")
        raise self.retry(exc=exc)


@shared_task(name="payments.sync_user_pending")
def sync_user_pending_task(user_id, since_hours=720):
    """
    Sync FimiPay orders za user mmoja.
    Inaitwa kwenye background baada ya webhook failure au manual.
    """
    from apps.accounts.models import User
    from apps.payments.services.status_sync import sync_user_pending

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return {"error": "user_not_found"}

    return sync_user_pending(user, since_hours=since_hours)