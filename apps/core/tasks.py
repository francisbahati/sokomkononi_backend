"""
Celery tasks for the core app.

    - purge_soft_deleted: hard-delete rows that have been in the
      recycle bin longer than SOFT_DELETE_RETENTION_DAYS.

Financial and audit records (ListingFee, ListingBoost, Reservation,
InspectionPeriod, Transaction, OTPVerification, Listing) are NEVER
purged by this task.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.apps import apps
from django.db.models import ProtectedError
from django.utils import timezone

from .constants import SOFT_DELETE_RETENTION_DAYS
from .models import SoftDeleteModel


logger = logging.getLogger(__name__)




@shared_task(name="core.purge_soft_deleted")
def purge_soft_deleted():
    """
    Hard-delete soft-deleted rows older than the retention window.
    """
    cutoff = timezone.now() - timedelta(
        days=SOFT_DELETE_RETENTION_DAYS
    )
    report = {}

    for model in apps.get_models():
        if (
            not issubclass(model, SoftDeleteModel)
            or model._meta.abstract
        ):
            continue

        if (model._meta.app_label, model.__name__) in AUDIT_PROTECTED_MODEL_NAMES:
            continue

        qs = model.all_objects.filter(
            is_deleted=True,
            deleted_at__lt=cutoff,
        )

        deleted = 0
        skipped = 0

        for obj in qs.iterator():
            try:
                _audit_purge(model, obj)
                obj.hard_delete()
                deleted += 1
            except ProtectedError:
                skipped += 1
                logger.warning(
                    "Cannot purge %s#%s — protected by a related row.",
                    model.__name__,
                    obj.pk,
                )

        if deleted or skipped:
            report[model.__name__] = {
                "deleted": deleted,
                "skipped": skipped,
            }

    logger.info("purge_soft_deleted: %s", report)
    return report

def _audit_purge(model, obj):
    """Write an AuditLog entry before a hard-delete via the purge task."""
    try:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            action="core.purge_soft_deleted",
            admin_user=None,
            admin_name="system",
            target=model.__name__,
            target_id=obj.pk,
            details=f"Hard-deleted after {SOFT_DELETE_RETENTION_DAYS} days in trash.",
        )
    except Exception:
        logger.exception("Failed to write audit log for purge of %s#%s",
                         model.__name__, obj.pk)
