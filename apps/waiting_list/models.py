from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class WaitingListEntry(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        NOTIFIED = "NOTIFIED", "Notified"
        CANCELLED = "CANCELLED", "Cancelled"
        FULFILLED = "FULFILLED", "Fulfilled"

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="waiting_list_entries",
        verbose_name="Tangazo",
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="waiting_list_entries",
        verbose_name="Mnunuzi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
        verbose_name="Hali",
    )

    position = models.PositiveIntegerField(
        default=1,
        verbose_name="Nafasi",
    )

    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kutaarifiwa",
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Muda wa kujiunga",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "waiting_list_entries"
        ordering = ["position", "joined_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["listing", "buyer"],
                name="unique_waiting_listing_buyer",
            ),
        ]

        indexes = [
            models.Index(
                fields=["listing", "status", "position"],
                name="wait_listing_status_pos_idx",
            ),
            models.Index(
                fields=["buyer", "status"],
                name="wait_buyer_status_idx",
            ),
            models.Index(
                fields=["status", "joined_at"],
                name="wait_status_joined_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Waiting List #{self.pk} - "
            f"{self.listing.title} - "
            f"{self.buyer.name}"
        )