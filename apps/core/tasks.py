from datetime import timedelta

from celery import shared_task
from django.apps import apps
from django.db.models import ProtectedError
from django.utils import timezone
import logging

from .constants import SOFT_DELETE_RETENTION_DAYS
from .models import SoftDeleteModel


logger = logging.getLogger(__name__)


@shared_task(name="core.purge_soft_deleted")
def purge_soft_deleted():
    cutoff = timezone.now() - timedelta(days=SOFT_DELETE_RETENTION_DAYS)
    report = {}

    for model in apps.get_models():
        if (
            not issubclass(model, SoftDeleteModel)
            or model._meta.abstract
        ):
            continue

        qs = model.all_objects.filter(
            is_deleted=True,
            deleted_at__lt=cutoff,
        )

        deleted = 0
        skipped = 0

        for obj in qs.iterator():
            try:
                obj.hard_delete()
                deleted += 1
            except ProtectedError:
                skipped += 1
                logger.warning(
                    "Cannot purge %s#%s — protected by a related row.",
                    model.__name__,
                    obj.pk,
                )

        report[model.__name__] = {
            "deleted": deleted,
            "skipped": skipped,
        }

    return report