from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import SoftDeleteModel


class BoostPackage(SoftDeleteModel):
    """
    Admin-configurable boost package.

    Example:
        1 Day  -> TZS 5,000
        3 Days -> TZS 12,000
        7 Days -> TZS 25,000
        14 Days -> TZS 40,000
    """

    name = models.CharField(
        max_length=100,
    )

    duration_hours = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Muda wa boost kwa saa.",
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Bei ya boost kwa TZS.",
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    ordering = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "boost_packages"
        ordering = ["ordering", "duration_hours", "price"]
        indexes = [
            models.Index(
                fields=["is_active", "ordering"],
                name="boost_pkg_active_order_idx",
            ),
        ]

        base_manager_name = "all_objects"
        default_manager_name = "objects"

        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_deleted=False),
                name="unique_active_boost_package_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} - TZS {self.price}"


class ListingBoost(models.Model):
    """
    Represents a seller's request/payment for boosting a listing.

    Financial record — never soft-deleted.
    """

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    class BoostStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.PROTECT,
        related_name="boosts",
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listing_boosts",
    )

    package = models.ForeignKey(
        BoostPackage,
        on_delete=models.PROTECT,
        related_name="listing_boosts",
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=BoostStatus.choices,
        default=BoostStatus.PENDING,
    )

    starts_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    expires_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "listing_boosts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["listing", "status"],
                name="boost_listing_status_idx",
            ),
            models.Index(
                fields=["seller", "status"],
                name="boost_seller_status_idx",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="boost_status_exp_idx",
            ),
            models.Index(
                fields=["payment_status", "created_at"],
                name="boost_pay_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Boost #{self.pk} - "
            f"{self.listing.title} - "
            f"{self.status}"
        )