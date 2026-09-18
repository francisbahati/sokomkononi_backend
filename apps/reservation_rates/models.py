from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ReservationRate(models.Model):
    """
    A reservation tier. "custom" tier is used for hours beyond the
    highest fixed tier (per-extra-day rate).
    """

    class Tier(models.TextChoices):
        H24 = "H24", "24 Hours"
        H48 = "H48", "48 Hours"
        H72 = "H72", "72 Hours"
        CUSTOM = "CUSTOM", "Custom (per day)"

    tier = models.CharField(
        max_length=10, choices=Tier.choices, unique=True,
    )
    hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Null for the custom tier.",
    )
    label_sw = models.CharField(max_length=100)
    label_en = models.CharField(max_length=100, blank=True)
    sub_sw = models.CharField(max_length=100, blank=True)
    sub_en = models.CharField(max_length=100, blank=True)

    fee = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "reservation_rates"
        ordering = ["ordering"]
        verbose_name = "Kiwango cha reservation"
        verbose_name_plural = "Viwango vya reservation"

    def __str__(self):
        return f"{self.tier} — TZS {self.fee}"
