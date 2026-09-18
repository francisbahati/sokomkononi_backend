from django.conf import settings
from django.db import models


class BannerAd(models.Model):
    """
    Records each seller's paid banner ad. Created after they pay the
    Advertisement Fee. The `expires_at` field drives the rotation window.
    """

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
    payment_reference = models.CharField(max_length=255, blank=True)

    active = models.BooleanField(default=True, verbose_name="Hai")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Inaisha")

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
