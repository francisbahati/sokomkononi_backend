"""
Celery tasks for the core app.

    - purge_soft_deleted: hard-delete rows that have been in the
      recycle bin longer than SOFT_DELETE_RETENTION_DAYS.
    - purge_soft_deleted_force: kama purge_soft_deleted, lakini
      inashughulikia pia AUDIT_PROTECTED_MODEL_NAMES (admin only).

Financial and audit records are NEVER purged by `purge_soft_deleted`
(default). `purge_soft_deleted_force` lazima iitwe kwa mkono na
superuser pekee.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.apps import apps
from django.db.models import ProtectedError
from django.utils import timezone

from .constants import (
    SOFT_DELETE_RETENTION_DAYS,
    AUDIT_PROTECTED_MODEL_NAMES,
)
from .models import SoftDeleteModel


logger = logging.getLogger(__name__)


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
        logger.exception(
            "Failed to write audit log for purge of %s#%s",
            model.__name__, obj.pk,
        )


def _purge_queryset(model, qs, force, report):
    """Hard-delete rows in `qs`; update `report` dict."""
    deleted = skipped = 0
    for obj in qs.iterator():
        try:
            obj.hard_delete()
            _audit_purge(model, obj)
            deleted += 1
        except ProtectedError:
            skipped += 1
            logger.warning(
                "Cannot purge %s#%s — protected by a related row.",
                model.__name__, obj.pk,
            )
    if deleted or skipped:
        report[model.__name__] = {"deleted": deleted, "skipped": skipped}


@shared_task(name="core.purge_soft_deleted")
def purge_soft_deleted():
    """
    Hard-delete soft-deleted rows older than the retention window.
    Inaruka AUDIT_PROTECTED_MODEL_NAMES (salama).
    """
    cutoff = timezone.now() - timedelta(days=SOFT_DELETE_RETENTION_DAYS)
    report = {}

    for model in apps.get_models():
        if not issubclass(model, SoftDeleteModel) or model._meta.abstract:
            continue
        if (model._meta.app_label, model.__name__) in AUDIT_PROTECTED_MODEL_NAMES:
            continue
        qs = model.all_objects.filter(is_deleted=True, deleted_at__lt=cutoff)
        _purge_queryset(model, qs, force=False, report=report)

    logger.info("purge_soft_deleted: %s", report)
    return report


@shared_task(name="core.purge_soft_deleted_force")
def purge_soft_deleted_force():
    """
    Kama purge_soft_deleted, lakini inashughulikia pia
    AUDIT_PROTECTED_MODEL_NAMES. Tumia kwa tahadhari kubwa —
    inaweza kufuta financial/audit records.
    """
    cutoff = timezone.now() - timedelta(days=SOFT_DELETE_RETENTION_DAYS)
    report = {}

    for model in apps.get_models():
        if not issubclass(model, SoftDeleteModel) or model._meta.abstract:
            continue
        qs = model.all_objects.filter(is_deleted=True, deleted_at__lt=cutoff)
        _purge_queryset(model, qs, force=True, report=report)

    logger.warning("purge_soft_deleted_force: %s", report)
    return report