# apps/finance/models.py
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class SuccessFeeConfig(models.Model):
    """
    Ada ya mafanikio + ada ya kupakua ripoti (PDF/CSV/DOC).
    Singleton (pk=1). Admin anaweza kubadilisha na ku-toggle.
    """
    key = models.CharField(
        max_length=50,
        unique=True,
        default="default",
        verbose_name="Ufunguo",
    )
    label_sw = models.CharField(
        max_length=100,
        default="Ada ya Mafanikio",
        verbose_name="Jina (Kiswahili)",
    )
    label_en = models.CharField(
        max_length=100,
        default="Success Fee",
        blank=True,
        verbose_name="Jina (Kiingereza)",
    )
    desc_sw = models.TextField(
        default="Ada ndogo ya kupakua ripoti ya miamala.",
        verbose_name="Maelezo (Kiswahili)",
        blank=True,
    )
    desc_en = models.TextField(
        default="Small fee to download transactions report.",
        verbose_name="Maelezo (Kiingereza)",
        blank=True,
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.0,
        verbose_name="Asilimia",
        help_text="Asilimia ya deal, mfano 2.0 kwa 2%.",
    )
    min_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=5000,
        verbose_name="Ada ya Chini (TZS)",
        help_text="Ada ya chini — pia flat fee kwa CSV/PDF download.",
    )
    max_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=500000,
        verbose_name="Ada ya Juu (TZS)",
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Inatumika",
        help_text="Kama False, hakuna ada ya mafanikio na download ni bure.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "success_fee_config"
        verbose_name = "Ada ya Mafanikio"
        verbose_name_plural = "Ada ya Mafanikio"

    def __str__(self):
        return f"Success Fee — {self.percentage}% (min TZS {self.min_fee})"


class SystemFeatureToggle(models.Model):
    """
    Toggles za jumla kwa mfumo:
    - listing_fee
    - reservation_fee
    - boost_fee
    - leading_fee
    - advertisement_fee
    - success_fee
    """
    key = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Ufunguo",
    )
    label_sw = models.CharField(
        max_length=100,
        verbose_name="Jina (Kiswahili)",
    )
    label_en = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Jina (Kiingereza)",
    )
    desc_sw = models.TextField(
        blank=True,
        verbose_name="Maelezo (Kiswahili)",
    )
    desc_en = models.TextField(
        blank=True,
        verbose_name="Maelezo (Kiingereza)",
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Inatumika",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_feature_toggles"
        verbose_name = "Kipengele cha Mfumo"
        verbose_name_plural = "Vipengele vya Mfumo"
        ordering = ["key"]

    def __str__(self):
        status = "ON" if self.is_enabled else "OFF"
        return f"{self.key} — {status}"


class SuccessFeePayment(models.Model):
    """
    One attempt to pay the success fee (transactions report download).

    Created PENDING when the user starts a payment, and marked PAID only
    by the FimiPay webhook (or by a server-side status check against
    FimiPay). The download endpoint trusts this table, never the client.

    Financial record - never deleted.
    """

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="success_fee_payments",
    )

    purpose = models.CharField(max_length=50, default="download")

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

    paid_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "success_fee_payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "payment_status", "paid_at"],
                name="sfp_user_status_paid_idx",
            ),
        ]

    def __str__(self):
        return f"SuccessFeePayment #{self.pk} - {self.user_id} - {self.payment_status}"