from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from .managers import SoftDeleteManager


class SoftDeleteModel(models.Model):
    """
    Abstract base for any model that supports the recycle bin.

    Notes:
        - `delete()` is a *soft* delete. It does NOT cascade to
          children via Django's collector. Children with a `CASCADE`
          FK remain alive. Use `on_delete=PROTECT` on any child
          that must never be orphaned.
        - `hard_delete()` bypasses the soft path entirely.
    """

    is_deleted = models.BooleanField(default=False, db_index=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    deletion_reason = models.TextField(blank=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager(include_deleted=True)

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
        default_manager_name = "objects"

    def delete(self, using=None, keep_parents=False, *, by=None, reason=""):
        if self.is_deleted:
            return (0, {})

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = by
        if reason:
            self.deletion_reason = reason

        self.save(update_fields=[
            "is_deleted", "deleted_at", "deleted_by", "deletion_reason",
        ])

        return (0, {})

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        if not self.is_deleted:
            return

        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = ""

        self.save(update_fields=[
            "is_deleted", "deleted_at", "deleted_by", "deletion_reason",
        ])

    @property
    def is_purgeable(self):
        if not self.is_deleted or not self.deleted_at:
            return False

        from .constants import SOFT_DELETE_RETENTION_DAYS
        return (
            timezone.now() - self.deleted_at
        ) >= timedelta(days=SOFT_DELETE_RETENTION_DAYS)