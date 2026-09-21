from django.db import models
from django.db.models.functions import Lower
from django.utils.text import slugify

from apps.core.models import SoftDeleteModel


class Category(SoftDeleteModel):
    name = models.CharField(max_length=100, verbose_name="Jina la kundi")

    slug = models.SlugField(
        max_length=120, blank=True, verbose_name="Slug",
    )

    description = models.TextField(blank=True, verbose_name="Maelezo")

    icon_key = models.CharField(
        max_length=50, blank=True,
        verbose_name="Ufunguo wa icon",
        help_text="Mfano: home, car, briefcase",
    )

    image_url = models.URLField(
        blank=True,
        verbose_name="URL ya picha",
    )

    is_popular = models.BooleanField(
        default=False,
        verbose_name="Maarufu",
    )

    extra = models.JSONField(
        default=dict, blank=True,
        verbose_name="Data ya ziada",
    )

    is_active = models.BooleanField(default=True, verbose_name="Lipo hai")

    ordering = models.PositiveIntegerField(
        default=0,
        verbose_name="Mpangilio",
        help_text="Namba ndogo huonekana kwanza.",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Imeundwa")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Imesasishwa")

    class Meta:
        db_table = "categories"
        ordering = ["ordering", "name"]
        verbose_name = "Kundi"
        verbose_name_plural = "Makundi"

        base_manager_name = "all_objects"
        default_manager_name = "objects"

        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                condition=models.Q(is_deleted=False),
                name="unique_active_category_name",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(is_deleted=False),
                name="unique_active_category_slug",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base = slugify(self.name) or "category"
        slug = base
        counter = 2

        while (
            Category.all_objects
            .filter(slug=slug, is_deleted=False)
            .exclude(pk=self.pk)
            .exists()
        ):
            slug = f"{base}-{counter}"
            counter += 1

        return slug

    def __str__(self):
        return self.name
