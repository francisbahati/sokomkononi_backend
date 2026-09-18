from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.deals.models import DealRoom
from apps.listings.models import Listing


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RESERVATION_PENDING = "RESERVATION_PENDING", "Reservation Pending"
        RESERVED = "RESERVED", "Reserved"
        INSPECTION = "INSPECTION", "Inspection"
        READY_FOR_FINAL_PAYMENT = (
            "READY_FOR_FINAL_PAYMENT", "Ready for Final Payment",
        )
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        DISPUTED = "DISPUTED", "Disputed"

    class BuyerDecision(models.TextChoices):
        PENDING = "PENDING", "Pending"
        READY_FOR_FINAL_PAYMENT = (
            "READY_FOR_FINAL_PAYMENT", "Ready for Final Payment",
        )
        NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED", "Not as Described"
        REQUEST_NEGOTIATION = (
            "REQUEST_NEGOTIATION", "Request Negotiation",
        )
        CANCEL_TRANSACTION = "CANCEL_TRANSACTION", "Cancel Transaction"

    deal_room = models.OneToOneField(
        DealRoom, on_delete=models.PROTECT,
        related_name="transaction", verbose_name="Deal Room",
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.PROTECT,
        related_name="transactions", verbose_name="Tangazo",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="purchase_transactions", verbose_name="Mnunuzi",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="sale_transactions", verbose_name="Muuzaji",
    )
    agreed_price = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Bei iliyokubaliwa",
    )
    status = models.CharField(
        max_length=30, choices=Status.choices,
        default=Status.RESERVATION_PENDING,
        verbose_name="Hali ya muamala",
    )
    buyer_decision = models.CharField(
        max_length=30, choices=BuyerDecision.choices,
        default=BuyerDecision.PENDING,
        verbose_name="Uamuzi wa mnunuzi",
    )
    buyer_decision_note = models.TextField(
        blank=True, verbose_name="Maelezo ya uamuzi wa mnunuzi",
    )
    buyer_decision_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa uamuzi wa mnunuzi",
    )
    final_payment_proof = models.FileField(
        upload_to="transactions/final-payment-proofs/",
        null=True, blank=True, verbose_name="Ushahidi wa malipo ya mwisho",
    )
    final_payment_reference = models.CharField(
        max_length=255, blank=True,
        verbose_name="Reference ya malipo ya mwisho",
    )
    final_payment_uploaded_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa kupakia ushahidi",
    )
    seller_confirmed_payment = models.BooleanField(
        default=False, verbose_name="Muuzaji amethibitisha malipo",
    )
    seller_confirmed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa uthibitisho wa muuzaji",
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa kukamilika",
    )
    cancelled_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa kughairiwa",
    )
    cancellation_reason = models.TextField(
        blank=True, verbose_name="Sababu ya kughairi",
    )
    dispute_resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="resolved_disputes",
        verbose_name="Mgogoro umetatuliwa na",
    )
    dispute_resolution_note = models.TextField(
        blank=True,
        verbose_name="Maelezo ya uamuzi wa mgogoro",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Imeundwa",
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["buyer", "status"],
                name="transaction_buyer_status_idx",
            ),
            models.Index(
                fields=["seller", "status"],
                name="transaction_seller_status_idx",
            ),
            models.Index(
                fields=["listing", "status"],
                name="transaction_listing_status_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="transaction_status_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Transaction #{self.pk} - "
            f"{self.listing.title} - {self.agreed_price}"
        )


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    transaction = models.OneToOneField(
        Transaction, on_delete=models.PROTECT,
        related_name="reservation", verbose_name="Muamala",
    )
    deposit_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Kiasi cha deposit",
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING, verbose_name="Hali ya malipo",
    )
    payment_reference = models.CharField(
        max_length=255, blank=True, verbose_name="Payment reference",
    )
    paid_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa kulipa",
    )
    duration_hours = models.PositiveIntegerField(
        default=48, verbose_name="Muda wa reservation kwa saa",
    )
    starts_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Reservation inaanza",
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Reservation inaisha",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        verbose_name="Hali ya reservation",
    )
    refund_reference = models.CharField(
        max_length=255, blank=True, verbose_name="Refund reference",
    )
    refunded_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa kurefund",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Imeundwa",
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "reservations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="reservation_status_exp_idx",
            ),
            models.Index(
                fields=["payment_status", "created_at"],
                name="res_pay_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Reservation #{self.pk} - "
            f"Transaction #{self.transaction_id}"
        )


class InspectionPeriod(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    transaction = models.OneToOneField(
        Transaction, on_delete=models.PROTECT,
        related_name="inspection_period", verbose_name="Muamala",
    )
    duration_hours = models.PositiveIntegerField(
        default=24, verbose_name="Muda wa inspection kwa saa",
    )
    starts_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Inspection inaanza",
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Inspection inaisha",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name="Hali ya inspection",
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Muda wa kukamilika",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Imeundwa",
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "inspection_periods"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="inspection_status_exp_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Inspection #{self.pk} - "
            f"Transaction #{self.transaction_id}"
        )