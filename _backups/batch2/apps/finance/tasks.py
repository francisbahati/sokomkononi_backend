import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task(name="finance.expire_stale_success_fee")
def expire_stale_success_fee():
    from apps.finance.models import SuccessFeePayment
    cutoff = timezone.now() - timedelta(days=30)
    n = SuccessFeePayment.objects.filter(
        payment_status=SuccessFeePayment.PaymentStatus.PENDING,
        created_at__lt=cutoff).update(
        payment_status=SuccessFeePayment.PaymentStatus.FAILED)
    logger.info("expire_stale_success_fee: %s", n)
    return {"expired": n}
