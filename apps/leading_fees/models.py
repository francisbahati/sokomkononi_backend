from decimal import Decimal

from django.db import models


class LeadingFeeConfig(models.Model):
    """
    Singleton (always pk=1). Editable by admins.
    """

    price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("10000"),
    )
    days = models.PositiveIntegerField(default=7)
    label_sw = models.CharField(max_length=100, default="Ada ya Kipaumbele")
    label_en = models.CharField(max_length=100, default="Leading Fee")
    desc_sw = models.TextField(
        default="Bidhaa yako inapanda juu ya matokeo ya utafutaji kwa siku 7",
    )
    desc_en = models.TextField(
        default="Your listing appears at the top of search results for 7 days",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leading_fee_config"
        verbose_name = "Ada ya Kipaumbele"
        verbose_name_plural = "Ada ya Kipaumbele"

    def __str__(self):
        return f"Leading Fee: TZS {self.price} / {self.days} days"
