from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Jina la kundi",
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        verbose_name="Slug",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Maelezo",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Lipo hai",
    )

    ordering = models.PositiveIntegerField(
        default=0,
        verbose_name="Mpangilio",
        help_text="Namba ndogo huonekana kwanza.",
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
        db_table = "categories"
        ordering = ["ordering", "name"]
        verbose_name = "Kundi"
        verbose_name_plural = "Makundi"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name