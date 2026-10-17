# apps/categories/migrations/0004_category_extra_fields.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0003_remove_category_unique_active_category_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="icon_key",
            field=models.CharField(
                max_length=60, blank=True,
                verbose_name="Icon key (lucide)",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="image_url",
            field=models.URLField(
                blank=True, null=True,
                verbose_name="Picha ya kuwakilisha",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="is_popular",
            field=models.BooleanField(
                default=True, verbose_name="Maarufu (navbar)",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="extra",
            field=models.JSONField(
                default=list, blank=True,
                verbose_name="Sehemu za ziada",
            ),
        ),
    ]
