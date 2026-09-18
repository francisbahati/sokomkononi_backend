from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class Lead(models.Model):
    """
    A buyer's enquiry about a listing. Created automatically when a
    DealRoom is opened between a buyer and seller for that listing.
    """

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        RESPONDED = "RESPONDED", "Responded"
        CONVERTED = "CONVERTED", "Converted"
        IGNORED = "IGNORED", "Ignored"

    class Source(models.TextChoices):
        MESSAGE = "MESSAGE", "Message"
        DEAL = "DEAL", "Deal Room"

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="leads",
        verbose_name="Tangazo",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_leads",
        verbose_name="Muuzaji",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_leads",
        verbose_name="Mnunuzi",
    )

    buyer_name = models.CharField(
        max_length=150,
        verbose_name="Jina la mnunuzi",
    )

    message = models.TextField(
        blank=True,
        verbose_name="Ujumbe",
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.DEAL,
        verbose_name="Chanzo",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name="Hali",
    )

    message_count = models.PositiveIntegerField(
        default=1,
        verbose_name="Idadi ya ujumbe",
    )

    deal_room = models.ForeignKey(
        "deals.DealRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name="Deal Room",
    )

    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kujibu",
    )
    converted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kubadilisha",
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
        db_table = "leads"
        ordering = ["-created_at"]
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

        indexes = [
            models.Index(
                fields=["seller", "status"],
                name="lead_seller_status_idx",
            ),
            models.Index(
                fields=["listing", "created_at"],
                name="lead_listing_created_idx",
            ),
            models.Index(
                fields=["buyer"],
                name="lead_buyer_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["listing", "buyer"],
                name="unique_lead_listing_buyer",
            ),
        ]

    def __str__(self):
        return f"Lead #{self.pk} — {self.listing.title} — {self.buyer_name}"