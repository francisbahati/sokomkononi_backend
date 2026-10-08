# apps/banners/models.py
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class BannerAd(models.Model):
    """
    Records each seller's paid banner ad. Created after they pay the
    Advertisement Fee. The `expires_at` field drives the rotation window.
    """
    package = models.ForeignKey(
        "advertisement_fees.AdvertisementPackage",
        on_delete=models.PROTECT,
        related_name="banner_ads",
        null=True,
        blank=True,
    )
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="banner_ads",
        verbose_name="Tangazo",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="banner_ads",
        verbose_name="Muuzaji",
    )

    listing_title = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    seller_name = models.CharField(max_length=150, blank=True)

    amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name="Kiasi kilicholipwa",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("PAID", "Paid"),
            ("FAILED", "Failed"),
            ("REFUNDED", "Refunded"),
        ],
        default="PENDING",
        verbose_name="Hali ya malipo",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(
        max_length=255, blank=True, null=True, unique=True,
    )

    active = models.BooleanField(default=True, verbose_name="Hai")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Inaisha",
    )

    class Meta:
        db_table = "banner_ads"
        ordering = ["-created_at"]
        verbose_name = "Tangazo la banner"
        verbose_name_plural = "Matangazo ya banner"

        indexes = [
            models.Index(
                fields=["active", "expires_at"],
                name="banner_active_exp_idx",
            ),
            models.Index(
                fields=["seller", "active"],
                name="banner_seller_active_idx",
            ),
        ]

    def __str__(self):
        return f"Banner #{self.pk} — {self.listing_title}"


class Campaign(models.Model):
    """
    Admin-managed promotional campaign. Inapunguza bei ya packages
    (Boost / Leading / Advertisement) kwa kipindi maalum.
    """

    class AppliesTo(models.TextChoices):
        BOOST = "BOOST", "Boost only"
        LEADING = "LEADING", "Leading only"
        ADVERTISEMENT = "ADVERTISEMENT", "Advertisement only"
        ALL = "ALL", "All promotions"

    # Legacy type (DISCOUNT/BANNER/FEATURE/OTHER) — tunaiweka kama
    # metadata. Haithiri pricing.
    class Type(models.TextChoices):
        DISCOUNT = "DISCOUNT", "Discount"
        BANNER = "BANNER", "Banner"
        FEATURE = "FEATURE", "Feature"
        OTHER = "OTHER", "Other"

    name = models.JSONField(
        default=dict,
        blank=True,
        help_text="Jina la kampeni: {sw, en}",
    )
    description = models.JSONField(
        default=dict,
        blank=True,
        help_text="Maelezo: {sw, en}",
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("100")),
        ],
        help_text="Punguzo kwa asilimia (0-100).",
    )

    applies_to = models.CharField(
        max_length=20,
        choices=AppliesTo.choices,
        default=AppliesTo.ALL,
        help_text="Inatumika kwa aina gani ya promotions.",
    )

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.DISCOUNT,
        help_text="Legacy type (DISCOUNT/BANNER/FEATURE/OTHER).",
    )

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    budget = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        default=Decimal("0.00"),
    )
    spent = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        default=Decimal("0.00"),
    )

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "campaigns"
        ordering = ["-created_at"]
        verbose_name = "Kampeni"
        verbose_name_plural = "Kampeni"

    def __str__(self):
        name = self.name.get("sw") or self.name.get("en") if isinstance(self.name, dict) else None
        return name or f"Campaign #{self.pk}"

    def is_live(self, at=None):
        from django.utils import timezone
        at = at or timezone.now()
        if not self.active:
            return False
        if self.start_date and self.start_date > at:
            return False
        if self.end_date and self.end_date < at:
            return False
        return True