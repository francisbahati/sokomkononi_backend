from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Bundle(models.Model):
    """
    Service bundle: packs of credits/services a seller can buy at
    a discount vs. buying each service individually.
    """

    class Type(models.TextChoices):
        LISTING = "LISTING", "Listing"
        LEADING = "LEADING", "Leading"
        BOOST = "BOOST", "Boost"
        RESERVATION = "RESERVATION", "Reservation"
        ADS = "ADS", "Ads"
        PREMIUM = "PREMIUM", "Premium"
        PACKAGE = "PACKAGE", "Package"

    code = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name="Code",
    )
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name="Aina",
    )

    name_sw = models.CharField(max_length=150, verbose_name="Jina (SW)")
    name_en = models.CharField(max_length=150, blank=True, verbose_name="Jina (EN)")
    description_sw = models.TextField(blank=True, verbose_name="Maelezo (SW)")
    description_en = models.TextField(blank=True, verbose_name="Maelezo (EN)")

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Bei",
    )

    # Either an integer or an object {"listing": 10, "boost": 3, ...}
    credits = models.JSONField(default=dict, blank=True, verbose_name="Credits")

    validity_days = models.PositiveIntegerField(
        default=90, verbose_name="Siku za uhalali"
    )

    # ["listing", "priority_visibility", "premium_badge", ...]
    services = models.JSONField(default=list, blank=True, verbose_name="Huduma")

    discount_percent = models.PositiveSmallIntegerField(
        default=0, verbose_name="Punguzo (%)"
    )

    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon")
    color = models.CharField(max_length=20, blank=True, verbose_name="Rangi")

    active = models.BooleanField(default=True, verbose_name="Hai")
    featured = models.BooleanField(default=False, verbose_name="Featured")
    ordering = models.PositiveIntegerField(default=0, verbose_name="Mpangilio")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bundles"
        ordering = ["ordering", "price"]
        verbose_name = "Kifurushi"
        verbose_name_plural = "Vifurushi"

        indexes = [
            models.Index(
                fields=["active", "ordering"],
                name="bundle_active_order_idx",
            ),
            models.Index(
                fields=["type", "active"],
                name="bundle_type_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name_sw or self.code} — TZS {self.price}"


class BundlePurchase(models.Model):
    """
    Record of a completed bundle purchase. Increments user credits
    via apps.credits.services.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bundle_purchases",
        verbose_name="Mtumiaji",
    )
    bundle = models.ForeignKey(
        Bundle,
        on_delete=models.PROTECT,
        related_name="purchases",
        verbose_name="Kifurushi",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Kiasi",
    )
    credits_snapshot = models.JSONField(default=dict, blank=True)
    services_snapshot = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Hali",
    )
    payment_reference = models.CharField(
        max_length=255, blank=True, null=True, unique=True,
        verbose_name="Payment reference",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bundle_purchases"
        ordering = ["-created_at"]
        verbose_name = "Ununuzi wa kifurushi"
        verbose_name_plural = "Manunuzi ya vifurushi"

        indexes = [
            models.Index(
                fields=["user", "status"],
                name="bpurchase_user_status_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="bpurchase_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.bundle.code} ({self.status})"
