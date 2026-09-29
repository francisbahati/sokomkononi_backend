"""
FimiPay-adjacent persistence layer.

The Payout model stores every merchant withdrawal SokoMkononi
requests from its FimiPay balance. A Celery task keeps the status
in sync with FimiPay.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REJECTED = "REJECTED", "Rejected"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fimipay_payouts",
        verbose_name="Iliundwa na",
    )

    withdrawal_id = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Withdrawal ID (FimiPay)",
    )

    amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Kiasi kilichoombwa",
    )
    fee = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        verbose_name="Ada",
    )
    net_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        null=True, blank=True,
        verbose_name="Kiasi halisi",
    )

    method = models.CharField(
        max_length=100,
        verbose_name="Njia (M-Pesa / CRDB Bank / ...)",
    )
    account_number = models.CharField(
        max_length=64,
        verbose_name="Namba ya akaunti",
    )
    account_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Jina la akaunti",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Hali",
    )
    fimi_status = models.CharField(
        max_length=30, blank=True,
        verbose_name="Hali ya FimiPay (raw)",
    )
    failure_reason = models.TextField(blank=True)

    raw_response = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fimipay_payouts"
        ordering = ["-created_at"]
        verbose_name = "Malipo ya kutoka (payout)"
        verbose_name_plural = "Malipo ya kutoka (payouts)"

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="payout_status_created_idx",
            ),
            models.Index(
                fields=["created_by", "status"],
                name="payout_user_status_idx",
            ),
        ]

    def __str__(self):
        return f"Payout #{self.pk} — {self.amount} — {self.status}"
