from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class SavedListing(models.Model):
    """
    A buyer's favorite listing. Stores a snapshot of price + status
    at save-time so we can notify about changes (price drop, sold, etc.).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_listings",
        verbose_name="Mtumiaji",
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="saved_by",
        verbose_name="Tangazo",
    )

    # Snapshot
    snapshot_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bei wakati wa kuhifadhi",
    )
    snapshot_status = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Hali wakati wa kuhifadhi",
    )
    snapshot_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Jina wakati wa kuhifadhi",
    )

    saved_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Muda wa kuhifadhi",
    )

    class Meta:
        db_table = "saved_listings"
        ordering = ["-saved_at"]
        verbose_name = "Tangazo lililohifadhiwa"
        verbose_name_plural = "Matangazo yaliyohifadhiwa"

        constraints = [
            models.UniqueConstraint(
                fields=["user", "listing"],
                name="unique_saved_user_listing",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "saved_at"],
                name="saved_user_time_idx",
            ),
            models.Index(
                fields=["listing"],
                name="saved_listing_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.listing}"