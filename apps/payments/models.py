"""
FimiPay-adjacent persistence layer.

The Payout model stores every merchant withdrawal SokoMkononi
requests from its FimiPay balance. A Celery task keeps the status
in sync with FimiPay.

Refund model inafuatilia refunds za promotions zilizofutwa.
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


class WebhookDiscrepancy(models.Model):
    """Records webhook events that fail verification (for reconciliation)."""
    order_id = models.CharField(max_length=64, db_index=True)
    prefix = models.CharField(max_length=10, blank=True)
    ref_id = models.IntegerField(null=True, blank=True)
    expected_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    reported_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    transid = models.CharField(max_length=128, blank=True)
    reason = models.CharField(max_length=64)
    raw_payload = models.JSONField(default=dict, blank=True)
    resolved = models.BooleanField(default=False)
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_discrepancies"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resolved", "created_at"]),
        ]


# ============================================================
# REFUND — kwa promotions zilizofutwa
# ============================================================
class Refund(models.Model):
    """
    Refund record kwa promotions zilizosimamishwa/kufutwa.

    Inafuatilia:
    - Ni promotion gani (type + id)
    - Ni mtumiaji gani
    - Namba yake ya malipo (snapshot)
    - Kiasi kilicholipwa
    - Kiasi kilichorudishwa
    - Hali (PENDING, PROCESSING, COMPLETED, FAILED)
    - Njia ya refund (manual, fimipay, credits)
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class Method(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        FIMIPAY = "FIMIPAY", "FimiPay"
        CREDITS = "CREDITS", "Credits"

    class PromotionType(models.TextChoices):
        BOOST = "BOOST", "Boost"
        LEADING = "LEADING", "Leading"
        ADVERTISE = "ADVERTISE", "Advertisement"
        RESERVATION = "RESERVATION", "Reservation"

    # ── Promotion inayohusika ──────────────────────────────
    promotion_type = models.CharField(
        max_length=20,
        choices=PromotionType.choices,
        verbose_name="Aina ya promotion",
    )
    promotion_id = models.PositiveBigIntegerField(
        verbose_name="ID ya promotion",
    )

    # ── Mtumiaji ───────────────────────────────────────────
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refunds",
        verbose_name="Mtumiaji",
    )

    # ── Snapshot ya taarifa za mtumiaji (wakati wa refund) ──
    user_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Namba ya simu",
    )
    user_email = models.EmailField(
        blank=True,
        verbose_name="Barua pepe",
    )
    user_payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Njia ya malipo (M-Pesa, Airtel, n.k.)",
    )

    # ── Kiasi ──────────────────────────────────────────────
    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Kiasi kilicholipwa",
    )
    amount_refunded = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Kiasi kilichorudishwa",
    )

    # ── Hali ───────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Hali",
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.MANUAL,
        verbose_name="Njia ya refund",
    )

    # ── Maelezo ────────────────────────────────────────────
    reason = models.TextField(
        blank=True,
        verbose_name="Sababu ya refund",
    )
    admin_note = models.TextField(
        blank=True,
        verbose_name="Maelezo ya admin",
    )

    # ── Admin aliyefanya ───────────────────────────────────
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds",
        verbose_name="Aliyefanya refund",
    )

    # ── Payment reference ──────────────────────────────────
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Kumbukumbu ya malipo",
    )
    refund_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Kumbukumbu ya refund",
    )

    # ── Timestamps ─────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "refunds"
        ordering = ["-created_at"]
        verbose_name = "Refund"
        verbose_name_plural = "Refunds"

        indexes = [
            models.Index(
                fields=["promotion_type", "promotion_id"],
                name="refund_promo_idx",
            ),
            models.Index(
                fields=["user", "status"],
                name="refund_user_status_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="refund_status_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Refund #{self.pk} — {self.promotion_type} "
            f"#{self.promotion_id} — {self.status}"
        )

    @property
    def is_completed(self):
        return self.status == self.Status.COMPLETED

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING