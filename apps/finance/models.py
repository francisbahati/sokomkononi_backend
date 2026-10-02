# apps/finance/models.py
from django.db import models


class SuccessFeeConfig(models.Model):
    """
    Ada ya mafanikio + ada ya kupakua ripoti (PDF/CSV/DOC).
    Singleton (pk=1). Admin anaweza kubadilisha na ku-toggle.
    """
    key = models.CharField(
        max_length=50,
        unique=True,
        default="default",
        verbose_name="Ufunguo",
    )
    label_sw = models.CharField(
        max_length=100,
        default="Ada ya Mafanikio",
        verbose_name="Jina (Kiswahili)",
    )
    label_en = models.CharField(
        max_length=100,
        default="Success Fee",
        blank=True,
        verbose_name="Jina (Kiingereza)",
    )
    desc_sw = models.TextField(
        default="Ada ndogo ya kupakua ripoti ya miamala.",
        verbose_name="Maelezo (Kiswahili)",
        blank=True,
    )
    desc_en = models.TextField(
        default="Small fee to download transactions report.",
        verbose_name="Maelezo (Kiingereza)",
        blank=True,
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.0,
        verbose_name="Asilimia",
        help_text="Asilimia ya deal, mfano 2.0 kwa 2%.",
    )
    min_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=5000,
        verbose_name="Ada ya Chini (TZS)",
        help_text="Ada ya chini — pia flat fee kwa CSV/PDF download.",
    )
    max_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=500000,
        verbose_name="Ada ya Juu (TZS)",
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Inatumika",
        help_text="Kama False, hakuna ada ya mafanikio na download ni bure.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "success_fee_config"
        verbose_name = "Ada ya Mafanikio"
        verbose_name_plural = "Ada ya Mafanikio"

    def __str__(self):
        return f"Success Fee — {self.percentage}% (min TZS {self.min_fee})"


class SystemFeatureToggle(models.Model):
    """
    Toggles za jumla kwa mfumo:
    - listing_fee
    - reservation_fee
    - boost_fee
    - leading_fee
    - advertisement_fee
    - success_fee
    """
    key = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Ufunguo",
    )
    label_sw = models.CharField(
        max_length=100,
        verbose_name="Jina (Kiswahili)",
    )
    label_en = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Jina (Kiingereza)",
    )
    desc_sw = models.TextField(
        blank=True,
        verbose_name="Maelezo (Kiswahili)",
    )
    desc_en = models.TextField(
        blank=True,
        verbose_name="Maelezo (Kiingereza)",
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Inatumika",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_feature_toggles"
        verbose_name = "Kipengele cha Mfumo"
        verbose_name_plural = "Vipengele vya Mfumo"
        ordering = ["key"]

    def __str__(self):
        status = "ON" if self.is_enabled else "OFF"
        return f"{self.key} — {status}"