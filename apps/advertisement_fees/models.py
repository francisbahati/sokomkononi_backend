from decimal import Decimal

from django.db import models


class AdvertisementFeeConfig(models.Model):
    """
    Singleton (always pk=1). Editable by admins.
    """

    price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("25000"),
    )
    days = models.PositiveIntegerField(default=7)
    label_sw = models.CharField(max_length=100, default="Ada ya Matangazo")
    label_en = models.CharField(max_length=100, default="Advertisement Fee")
    desc_sw = models.TextField(
        default="Banner inayozunguka kwenye Dashboard (5s rotation) kwa siku 7",
    )
    desc_en = models.TextField(
        default="Rotating banner on the Dashboard (5s rotation) for 7 days",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "advertisement_fee_config"
        verbose_name = "Ada ya Matangazo"
        verbose_name_plural = "Ada ya Matangazo"

    def __str__(self):
        return f"Advertisement Fee: TZS {self.price} / {self.days} days"
