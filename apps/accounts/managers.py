from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone


class UserQuerySet(models.QuerySet):
    """
    User queryset with bulk-delete override.

    A bulk User.objects.filter(...).delete() must tombstone the
    unique email so new accounts can register with it again.
    """

    def delete(self, *, by=None, reason="", **kwargs):
        # Snapshot emails first — we need them for `deleted_email`.
        rows = list(self.values_list("pk", "email"))
        for pk, email in rows:
            if email:
                self.model.all_objects.filter(pk=pk).update(
                    deleted_email=email, email=None,
                )
        return self.update(
            is_deleted=True,
            deleted_at=timezone.now(),
            deleted_by=by,
            deletion_reason=reason or "",
        )


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    """
    Default manager for the custom User model.

    Hides soft-deleted users. Use `User.all_objects` to see every
    user including those in the recycle bin.
    """

    use_in_migrations = True

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def hard_queryset(self):
        return super().get_queryset()

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")

        email = self.normalize_email(email).lower()

        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_user_by_phone(self, phone, name, password=None, **extra_fields):
        """
        Create a phone-only user (no email).
        """
        if not phone:
            raise ValueError("Phone is required.")

        if not name:
            raise ValueError("Name is required.")

        user = self.model(
            email=None,
            phone=phone,
            name=name,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email=email, password=password, **extra_fields)