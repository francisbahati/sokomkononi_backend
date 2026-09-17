from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel

from .managers import UserManager


class User(SoftDeleteModel, AbstractBaseUser, PermissionsMixin):

    class AccountType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        BUSINESS = "BUSINESS", "Business"

    name = models.CharField(
        max_length=150,
        verbose_name="Jina kamili",
    )

    email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="Barua pepe",
    )

    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Namba ya simu",
    )

    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.INDIVIDUAL,
        verbose_name="Aina ya akaunti",
    )

    is_verified = models.BooleanField(
        default=False,
        help_text="Account must be verified before full access.",
        verbose_name="Imethibitishwa",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ipo hai",
    )

    is_staff = models.BooleanField(
        default=False,
        verbose_name="Ni staff",
    )

    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name="Tarehe ya kujiunga",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Imesasishwa",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        verbose_name = "Mtumiaji"
        verbose_name_plural = "Watumiaji"

        base_manager_name = "all_objects"
        default_manager_name = "objects"

        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(
                    is_deleted=False,
                    email__isnull=False,
                ),
                name="unique_active_user_email",
            ),
            models.UniqueConstraint(
                fields=["phone"],
                condition=models.Q(
                    is_deleted=False,
                    phone__isnull=False,
                ),
                name="unique_active_user_phone",
            ),
        ]

    def __str__(self):
        return (
            self.name
            or self.email
            or self.phone
            or f"User {self.pk}"
        )

    @property
    def can_buy(self):
        return (
            self.is_active
            and self.is_verified
            and not self.is_deleted
        )

    @property
    def can_sell(self):
        return (
            self.is_active
            and self.is_verified
            and not self.is_deleted
        )


class PendingRegistration(models.Model):

    name = models.CharField(
        max_length=150,
        verbose_name="Jina kamili",
    )

    email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="Barua pepe",
    )

    phone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Namba ya simu",
    )

    account_type = models.CharField(
        max_length=20,
        choices=User.AccountType.choices,
        default=User.AccountType.INDIVIDUAL,
        verbose_name="Aina ya akaunti",
    )

    password_hash = models.CharField(
        max_length=128,
        verbose_name="Hash ya nenosiri",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "pending_registrations"
        ordering = ["-created_at"]
        verbose_name = "Usajili unaosubiri"
        verbose_name_plural = "Usajili unaosubiri"

    def __str__(self):
        return (
            self.email
            or self.phone
            or self.name
            or f"Pending registration {self.pk}"
        )


class OTPVerification(models.Model):

    class VerificationType(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        PHONE = "PHONE", "Phone"
        PASSWORD_RESET_EMAIL = (
            "PASSWORD_RESET_EMAIL",
            "Password Reset (Email)",
        )
        PASSWORD_RESET_PHONE = (
            "PASSWORD_RESET_PHONE",
            "Password Reset (Phone)",
        )

    identifier = models.CharField(
        max_length=254,
        db_index=True,
        verbose_name="Email au namba ya simu",
    )

    verification_type = models.CharField(
        max_length=30,
        choices=VerificationType.choices,
        verbose_name="Aina ya uthibitishaji",
    )

    otp_code = models.CharField(
        max_length=64,
        verbose_name="OTP",
        help_text="OTP is stored as SHA-256 hash.",
    )

    is_used = models.BooleanField(
        default=False,
        verbose_name="Imetumika",
    )

    attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Idadi ya majaribio",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    expires_at = models.DateTimeField(
        verbose_name="Inaisha",
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Imethibitishwa",
    )

    class Meta:
        db_table = "otp_verifications"
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "identifier",
                    "verification_type",
                    "is_used",
                ],
                name="otp_identifier_type_used_idx",
            ),
        ]

        verbose_name = "Uthibitishaji wa OTP"
        verbose_name_plural = "Uthibitishaji wa OTP"

    def __str__(self):
        return (
            f"{self.verification_type}: "
            f"{self.identifier}"
        )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return (
            not self.is_used
            and not self.is_expired
        )