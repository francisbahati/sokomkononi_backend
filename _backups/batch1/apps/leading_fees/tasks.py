import logging

from celery import shared_task

from .services.leading import expire_stale_leading


logger = logging.getLogger(__name__)


@shared_task(name="leading_fees.expire_stale_leading")
def expire_stale_leading_task():
    count = expire_stale_leading()
    logger.info("expire_stale_leading: %s leadings expired", count)
    return {"expired": count}
