from django.conf import settings
from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        GENERAL = "GENERAL", "General"

        LISTING_CREATED = "LISTING_CREATED", "Listing Created"
        LISTING_APPROVED = "LISTING_APPROVED", "Listing Approved"
        LISTING_REJECTED = "LISTING_REJECTED", "Listing Rejected"

        NEW_OFFER = "NEW_OFFER", "New Offer"
        OFFER_COUNTERED = "OFFER_COUNTERED", "Offer Countered"
        OFFER_ACCEPTED = "OFFER_ACCEPTED", "Offer Accepted"

        TRANSACTION_CREATED = "TRANSACTION_CREATED", "Transaction Created"

        RESERVATION_CREATED = "RESERVATION_CREATED", "Reservation Created"
        RESERVATION_PAID = "RESERVATION_PAID", "Reservation Paid"
        RESERVATION_EXPIRING = "RESERVATION_EXPIRING", "Reservation Expiring"
        RESERVATION_EXPIRED = "RESERVATION_EXPIRED", "Reservation Expired"

        INSPECTION_STARTED = "INSPECTION_STARTED", "Inspection Started"
        INSPECTION_COMPLETED = "INSPECTION_COMPLETED", "Inspection Completed"

        BUYER_DECISION = "BUYER_DECISION", "Buyer Decision"

        PAYMENT_PROOF_UPLOADED = (
            "PAYMENT_PROOF_UPLOADED",
            "Payment Proof Uploaded",
        )

        PAYMENT_CONFIRMED = (
            "PAYMENT_CONFIRMED",
            "Payment Confirmed",
        )

        TRANSACTION_COMPLETED = (
            "TRANSACTION_COMPLETED",
            "Transaction Completed",
        )

        TRANSACTION_CANCELLED = (
            "TRANSACTION_CANCELLED",
            "Transaction Cancelled",
        )

        WAITING_LIST_JOINED = (
            "WAITING_LIST_JOINED",
            "Waiting List Joined",
        )

        WAITING_LIST_AVAILABLE = (
            "WAITING_LIST_AVAILABLE",
            "Waiting List Available",
        )

        BOOST_ACTIVATED = (
            "BOOST_ACTIVATED",
            "Boost Activated",
        )

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Mpokeaji",
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        verbose_name="Aina ya arifa",
    )

    title = models.CharField(
        max_length=255,
        verbose_name="Kichwa",
    )

    message = models.TextField(
        verbose_name="Ujumbe",
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        verbose_name="Kipaumbele",
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name="Imesomwa",
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kusomwa",
    )

    # Optional reference to an object related to the notification.
    # Example: listing ID, deal room ID, transaction ID, etc.
    related_object_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Aina ya kitu kinachohusiana",
    )

    related_object_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID ya kitu kinachohusiana",
    )

    action_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Kiungo cha hatua",
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
        db_table = "notifications"
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["recipient", "is_read", "created_at"],
                name="notif_recipient_read_idx",
            ),
            models.Index(
                fields=["recipient", "notification_type"],
                name="notif_recipient_type_idx",
            ),
            models.Index(
                fields=["priority", "created_at"],
                name="notif_priority_created_idx",
            ),
            models.Index(
                fields=["related_object_type", "related_object_id"],
                name="notif_related_obj_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} → {self.recipient.name}"