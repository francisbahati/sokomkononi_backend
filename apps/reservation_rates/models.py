# apps/reservation_rates/models.py
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ReservationSettings(models.Model):
    """
    Singleton (pk=1). Inahifadhi is_enabled tu kwa reservation system.
    Kama is_enabled=False, tiers zote zinakuwa BURE (fee=0).
    """
    is_enabled = models.BooleanField(
        default=True,
        help_text="Kama False, reservation ni bure kwa tiers zote.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reservation_settings"
        verbose_name = "Reservation Settings"
        verbose_name_plural = "Reservation Settings"

    def __str__(self):
        return f"Reservation: {'ON' if self.is_enabled else 'OFF'}"


class ReservationTier(models.Model):
    """
    Tier moja ya reservation — hours + fee.
    Admin anaweza kuongeza/kufuta/kubadilisha.
    """
    hours = models.PositiveIntegerField(
        help_text="Muda wa reservation kwa masaa (mf. 12, 24, 168).",
    )
    fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("1000"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Bei ya tier kwa TZS.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Kama False, tier haionekani kwenye dropdown.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Mpangilio wa kuonyesha (ndogo kwanza).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reservation_tier"
        ordering = ["order", "hours"]
        verbose_name = "Reservation Tier"
        verbose_name_plural = "Reservation Tiers"
        constraints = [
            models.UniqueConstraint(
                fields=["hours"],
                name="unique_reservation_tier_hours",
            ),
        ]

    def __str__(self):
        return f"{self.hours}h — TZS {self.fee}"