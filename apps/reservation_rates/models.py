# apps/reservation_rates/models.py
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ReservationRate(models.Model):
    """
    Flat fee kwa reservation. Singleton (pk=1).
    Admin anaweza ku-toggle on/off.
    """
    flat_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("50000"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Flat fee ya reservation kwa TZS.",
    )
    days = models.PositiveIntegerField(
        default=3,
        help_text="Idadi ya siku reservation inadumu.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Kama False, reservation ni bure.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reservation_rate_config"
        verbose_name = "Ada ya Reservation"
        verbose_name_plural = "Ada ya Reservation"

    def __str__(self):
        return f"Reservation: TZS {self.flat_fee} / {self.days} days"