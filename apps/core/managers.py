from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """Queryset that hides soft-deleted rows by default."""

    def delete(self):
        """Bulk soft delete."""
        return self.update(
            is_deleted=True,
            deleted_at=timezone.now(),
        )

    def hard_delete(self):
        """Really delete rows (used by the purge task only)."""
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)

    def restore(self):
        return self.update(
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            deletion_reason="",
        )


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """
    Default manager. Hides soft-deleted rows.

    `SoftDeleteManager(include_deleted=True)` returns *all* rows.
    """

    def __init__(self, *args, include_deleted=False, **kwargs):
        self.include_deleted = include_deleted
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.include_deleted:
            return qs
        return qs.filter(is_deleted=False)