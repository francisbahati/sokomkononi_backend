from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Default manager for the custom User model.

    Hides soft-deleted users. Use `User.all_objects` to see
    every user including those in the recycle bin.
    """

    use_in_migrations = True

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(is_deleted=False)
        )

    def hard_queryset(self):
        """Every row, including soft-deleted."""
        return super().get_queryset()

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_user(
        self,
        email,
        password=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("Email is required.")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        email,
        password=None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(
                "Superuser must have is_staff=True."
            )

        if extra_fields.get("is_superuser") is not True:
            raise ValueError(
                "Superuser must have is_superuser=True."
            )

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )