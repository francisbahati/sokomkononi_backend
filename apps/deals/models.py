from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.listings.models import Listing


class DealRoom(models.Model):
    """
    Mazungumzo ya ununuzi kati ya mnunuzi na muuzaji
    kuhusu tangazo moja.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        NEGOTIATING = "NEGOTIATING", "Negotiating"
        AGREED = "AGREED", "Agreed"
        CANCELLED = "CANCELLED", "Cancelled"
        CLOSED = "CLOSED", "Closed"

    listing = models.ForeignKey(
        Listing,
        on_delete=models.PROTECT,
        related_name="deal_rooms",
        verbose_name="Tangazo",
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="seller_deal_rooms",
        verbose_name="Muuzaji",
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="buyer_deal_rooms",
        verbose_name="Mnunuzi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Hali",
    )

    agreed_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Bei iliyokubaliwa",
    )

    agreed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kukubaliana",
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
        db_table = "deal_rooms"
        ordering = ["-updated_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["listing", "buyer"],
                name="unique_deal_room_listing_buyer",
            ),
        ]

        indexes = [
            models.Index(
                fields=["seller", "status"],
                name="deal_seller_status_idx",
            ),
            models.Index(
                fields=["buyer", "status"],
                name="deal_buyer_status_idx",
            ),
            models.Index(
                fields=["listing", "status"],
                name="deal_listing_status_idx",
            ),
            models.Index(
                fields=["status", "updated_at"],
                name="deal_status_updated_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Deal Room #{self.pk} - "
            f"{self.listing.title} - "
            f"{self.buyer.name}"
        )


class NegotiationOffer(models.Model):
    """
    Huhifadhi kila offer/counter-offer ndani ya Deal Room.

    Hakuna offer inayofutwa au kubadilishwa.
    Hii inatunza historia kamili ya negotiation.
    """

    class OfferedBy(models.TextChoices):
        BUYER = "BUYER", "Buyer"
        SELLER = "SELLER", "Seller"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        COUNTERED = "COUNTERED", "Countered"
        CANCELLED = "CANCELLED", "Cancelled"

    deal_room = models.ForeignKey(
        DealRoom,
        on_delete=models.CASCADE,
        related_name="offers",
        verbose_name="Deal Room",
    )

    offered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="negotiation_offers",
        verbose_name="Aliyetoa offer",
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
        verbose_name="Kiasi cha offer",
    )

    message = models.TextField(
        blank=True,
        verbose_name="Ujumbe",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Hali ya offer",
    )

    responded_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses",
        verbose_name="Offer iliyojibiwa",
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
        db_table = "negotiation_offers"
        ordering = ["created_at"]

        indexes = [
            models.Index(
                fields=["deal_room", "created_at"],
                name="offer_deal_created_idx",
            ),
            models.Index(
                fields=["offered_by", "created_at"],
                name="offer_user_created_idx",
            ),
            models.Index(
                fields=["deal_room", "status"],
                name="offer_deal_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Offer #{self.pk} - "
            f"{self.amount} - "
            f"{self.offered_by.name}"
        )