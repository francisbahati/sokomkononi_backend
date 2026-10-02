# apps/leading_fees/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models


class LeadingFeeConfig(models.Model):
    """Singleton (pk=1). Admin editable."""

    price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("10000"),
    )
    days = models.PositiveIntegerField(default=7)
    label_sw = models.CharField(max_length=100, default="Ada ya Kipaumbele")
    label_en = models.CharField(max_length=100, default="Leading Fee")
    desc_sw = models.TextField(
        default="Bidhaa yako inapanda juu ya matokeo ya utafutaji kwa siku 7",
    )
    desc_en = models.TextField(
        default="Your listing appears at the top of search results for 7 days",
    )

    # ⬇️ MPYA
    is_enabled = models.BooleanField(
        default=True,
        help_text="Kama False, leading haitozwi.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leading_fee_config"
        verbose_name = "Ada ya Kipaumbele"
        verbose_name_plural = "Ada ya Kipaumbele"

    def __str__(self):
        return f"Leading Fee: TZS {self.price} / {self.days} days"


class ListingLeading(models.Model):
    """A purchase of a leading slot for one listing."""

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.PROTECT,
        related_name="leading_purchases",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leading_purchases",
    )
    days = models.PositiveIntegerField(default=7)
    price = models.DecimalField(max_digits=15, decimal_places=2)
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
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "listing_leadings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["listing", "status"],
                name="leading_listing_status_idx",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="leading_status_exp_idx",
            ),
            models.Index(
                fields=["seller", "status"],
                name="leading_seller_status_idx",
            ),
        ]

    def __str__(self):
        return f"Leading #{self.pk} — {self.listing_id} — {self.status}"