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

    # ----------------------------------------------------------------
    # Unique unconditionally so Django's auth system accepts it as
    # USERNAME_FIELD. Soft-delete tombstones it to free it up.
    # ----------------------------------------------------------------
    email = models.EmailField(
        null=True,
        blank=True,
        unique=True,
        verbose_name="Barua pepe",
    )

    # Holds the original email of a soft-deleted user so it can be
    # reclaimed on restore, while keeping `email` free for reuse.
    deleted_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="Barua pepe ya awali",
    )

    # Contact info only. Unique among active users (see constraint
    # below) but never used for OTP, verification or login.
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

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        verbose_name="Picha ya wasifu",
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
            or self.deleted_email
            or f"User {self.pk}"
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Soft-delete override — tombstone the unique email
    # ------------------------------------------------------------------

    def delete(self, using=None, keep_parents=False, *, by=None, reason=""):
        """
        Soft-delete the user and free up the unique email so a new
        account can register with it immediately.

        The original email is preserved in `deleted_email` and can be
        reclaimed via `restore()` if it's still free.
        """
        if self.is_deleted:
            return (0, {})

        if self.email:
            self.deleted_email = self.email
            self.email = None

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = by
        if reason:
            self.deletion_reason = reason

        self.save(
            update_fields=[
                "email",
                "deleted_email",
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "deletion_reason",
            ]
        )

        return (0, {})

    def restore(self):
        """
        Restore the user and reclaim the original email if it's still
        available. If someone else has taken it, the original is
        dropped and the user must set a new email.
        """
        if not self.is_deleted:
            return

        if self.deleted_email and not self.email:
            email_taken = (
                User.all_objects
                .filter(email=self.deleted_email)
                .exclude(pk=self.pk)
                .exists()
            )

            if not email_taken:
                self.email = self.deleted_email

            # Clear deleted_email either way — either reclaimed or lost.
            self.deleted_email = None

        # If the phone has been reclaimed by another active user,
        # drop it so the unique_active_user_phone constraint holds.
        if self.phone:
            phone_taken = (
                User.all_objects
                .filter(phone=self.phone, is_deleted=False)
                .exclude(pk=self.pk)
                .exists()
            )
            if phone_taken:
                self.phone = None

        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = ""

        self.save(
            update_fields=[
                "email",
                "deleted_email",
                "phone",
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "deletion_reason",
            ]
        )


class PendingRegistration(models.Model):

    name = models.CharField(
        max_length=150,
        verbose_name="Jina kamili",
    )

    email = models.EmailField(
        unique=True,
        verbose_name="Barua pepe",
    )

    # Contact info only, carried over to User on verification.
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
        return self.email or self.name or f"Pending registration {self.pk}"


class OTPVerification(models.Model):

    class VerificationType(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        PASSWORD_RESET_EMAIL = (
            "PASSWORD_RESET_EMAIL",
            "Password Reset (Email)",
        )

    identifier = models.CharField(
        max_length=254,
        db_index=True,
        verbose_name="Barua pepe",
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


# ============================================================
# USER PREFERENCES — singleton per user
# ============================================================
class UserPreferences(models.Model):
    """
    Mapendeleo ya mtumiaji. Moja kwa kila user (OneToOne).
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    language = models.CharField(
        max_length=5,
        choices=[("sw", "Kiswahili"), ("en", "English")],
        default="sw",
    )
    currency = models.CharField(
        max_length=5,
        choices=[("TZS", "Tanzanian Shilling"), ("USD", "US Dollar")],
        default="TZS",
    )
    region = models.CharField(max_length=100, default="Dar es Salaam")
    show_phone = models.BooleanField(default=True)
    show_email = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_preferences"
        verbose_name = "User Preferences"
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"Preferences — {self.user_id}"


# ============================================================
# NOTIFICATION PREFERENCES — singleton per user
# ============================================================
class NotificationPreference(models.Model):
    """
    Mipangilio ya taarifa. Moja kwa kila user (OneToOne).
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    # Email
    email_deals = models.BooleanField(default=True)
    email_messages = models.BooleanField(default=True)
    email_promotions = models.BooleanField(default=False)
    email_newsletter = models.BooleanField(default=True)
    # SMS
    sms_deals = models.BooleanField(default=True)
    sms_messages = models.BooleanField(default=False)
    sms_promotions = models.BooleanField(default=False)
    # Push
    push_deals = models.BooleanField(default=True)
    push_messages = models.BooleanField(default=True)
    push_promotions = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_notification_preferences"
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"NotificationPrefs — {self.user_id}"