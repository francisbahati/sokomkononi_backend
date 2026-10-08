# apps/advertisement_fees/models.py
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class AdvertisementFeeConfig(models.Model):
    """
    Singleton (pk=1): global on/off switch kwa advertisement fee.
    Kama is_enabled=False, matangazo ni BURE.
    """
    is_enabled = models.BooleanField(
        default=True,
        help_text="Kama False, matangazo hayatozwi (ni bure).",
    )
    label_sw = models.CharField(max_length=100, default="Ada ya Matangazo")
    label_en = models.CharField(max_length=100, default="Advertisement Fee")
    desc_sw = models.TextField(
        default="Banner inayozunguka kwenye Dashboard kwa siku 7",
    )
    desc_en = models.TextField(
        default="Rotating banner on the Dashboard for 7 days",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "advertisement_fee_config"
        verbose_name = "Ada ya Matangazo"
        verbose_name_plural = "Ada ya Matangazo"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Advertisement Fee: {'ON' if self.is_enabled else 'OFF (free)'}"


class AdvertisementPackage(models.Model):
    """
    Advertisement package ya admin-configurable.
    """
    name = models.CharField(
        max_length=100,
        help_text="Mfano: Starter, Standard, Premium",
    )
    duration_hours = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Muda wa tangazo kwa saa (24 = siku 1).",
    )
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Bei kwa TZS.",
    )
    description = models.TextField(
        blank=True,
        help_text="Maelezo ya ziada (optional).",
    )
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "advertisement_packages"
        ordering = ["ordering", "duration_hours", "price"]
        verbose_name = "Advertisement Package"
        verbose_name_plural = "Advertisement Packages"
        indexes = [
            models.Index(
                fields=["is_active", "ordering"],
                name="ad_pkg_active_order_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="unique_advertisement_package_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} - TZS {self.price} / {self.duration_hours}h"