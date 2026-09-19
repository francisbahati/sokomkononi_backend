from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        count = self.update(
            is_deleted=True,
            deleted_at=timezone.now(),
        )
        return (count, {})

    def hard_delete(self):
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
    use_in_migrations = True

    def __init__(self, *args, include_deleted=False, **kwargs):
        self.include_deleted = include_deleted
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.include_deleted:
            kwargs["include_deleted"] = True
        return path, args, kwargs

    def get_queryset(self):
        qs = super().get_queryset()
        if self.include_deleted:
            return qs
        return qs.filter(is_deleted=False)
