
from django.conf import settings
from django.db import models
from django.utils import timezone

from .managers import SoftDeleteManager


class SoftDeleteModel(models.Model):
    """Abstract base for any model that supports the recycle bin."""

    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    deletion_reason = models.TextField(
        blank=True,
    )

    # Default manager hides deleted rows.
    objects = SoftDeleteManager()

    # Escape hatch: see everything.
    all_objects = SoftDeleteManager(include_deleted=True)

    class Meta:
        abstract = True
        # `base_manager` is used for FK traversal and reverse relations.
        # We want `listing.category` to still resolve even when the
        # category is in the recycle bin.
        base_manager_name = "all_objects"
        default_manager_name = "objects"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def delete(self, using=None, keep_parents=False, *, by=None, reason=""):
        """Soft delete — never destroys the row."""
        if self.is_deleted:
            return (0, {})

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = by
        if reason:
            self.deletion_reason = reason

        self.save(
            update_fields=[
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "deletion_reason",
            ]
        )

        return (0, {})

    def hard_delete(self, using=None, keep_parents=False):
        """Really remove the row. Use only from the purge task."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        if not self.is_deleted:
            return

        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = ""

        self.save(
            update_fields=[
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "deletion_reason",
            ]
        )

    @property
    def is_purgeable(self):
        if not self.is_deleted or not self.deleted_at:
            return False

        from .constants import SOFT_DELETE_RETENTION_DAYS
        from datetime import timedelta

        return (
            timezone.now() - self.deleted_at
        ) >= timedelta(days=SOFT_DELETE_RETENTION_DAYS)