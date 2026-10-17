from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self, *, by=None, reason="", **kwargs):
        """Bulk soft-delete. Only touches currently-alive rows."""
        now = timezone.now()
        count = self.filter(is_deleted=False).update(
            is_deleted=True,
            deleted_at=now,
            updated_at=now,
            deleted_by=by,
            deletion_reason=reason or "",
        )
        return (count, {self.model._meta.label: count})

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)

    def restore(self):
        now = timezone.now()
        return self.filter(is_deleted=True).update(
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            deletion_reason="",
            updated_at=now,
        )


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    use_in_migrations = True

    def __init__(self, *args, include_deleted=False, **kwargs):
        self.include_deleted = include_deleted
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        as_manager, manager_path, qs_path, args, kwargs = super().deconstruct()
        if self.include_deleted:
            kwargs["include_deleted"] = True
        return as_manager, manager_path, qs_path, args, kwargs

    def get_queryset(self):
        qs = super().get_queryset()
        if self.include_deleted:
            return qs
        return qs.filter(is_deleted=False)
