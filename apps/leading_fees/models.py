# apps/leading_fees/models.py
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class LeadingFeeConfig(models.Model):
    """
    Singleton (pk=1): global on/off switch kwa leading fee.
    Kama is_enabled=False, leading ni BURE kwa wote (packages
    bado zinaonekana lakini hazitozi).
    """
    is_enabled = models.BooleanField(
        default=True,
        help_text="Kama False, leading haitozwi (ni bure).",
    )
    label_sw = models.CharField(max_length=100, default="Ada ya Kipaumbele")
    label_en = models.CharField(max_length=100, default="Leading Fee")
    desc_sw = models.TextField(
        default="Bidhaa yako inapanda juu ya matokeo ya utafutaji",
    )
    desc_en = models.TextField(
        default="Your listing appears at the top of search results",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leading_fee_config"
        verbose_name = "Ada ya Kipaumbele"
        verbose_name_plural = "Ada ya Kipaumbele"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Leading Fee: {'ON' if self.is_enabled else 'OFF (free)'}"


class LeadingPackage(models.Model):
    """
    Leading package ya admin-configurable.
    Mfano: Starter 1 day, Standard 3 days, Premium 7 days.
    """
    name = models.CharField(
        max_length=100,
        help_text="Mfano: Starter, Standard, Premium",
    )
    duration_hours = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Muda wa leading kwa saa (24 = siku 1).",
    )
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Bei kwa TZS.",
    )
    description = models.TextField(
        blank=True,
        help_text="Maelezo ya ziada (optional).",
    )
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leading_packages"
        ordering = ["ordering", "duration_hours", "price"]
        verbose_name = "Leading Package"
        verbose_name_plural = "Leading Packages"
        indexes = [
            models.Index(
                fields=["is_active", "ordering"],
                name="lead_pkg_active_order_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="unique_leading_package_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} - TZS {self.price} / {self.duration_hours}h"


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
    package = models.ForeignKey(
        LeadingPackage,
        on_delete=models.PROTECT,
        related_name="listing_leadings",
        null=True,
        blank=True,
    )
    days = models.PositiveIntegerField(default=7)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
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