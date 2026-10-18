# apps/reservation_rates/migrations/0002_change_to_flat_fee.py
import django.core.validators
from decimal import Decimal
from django.db import migrations, models


def forward_migration(apps, schema_editor):
    """Futa rows zote za kale na unda singleton mpya."""
    ReservationRate = apps.get_model("reservation_rates", "ReservationRate")
    ReservationRate.objects.all().delete()
    ReservationRate.objects.create(
        flat_fee=Decimal("11000"),
        days=3,
        is_enabled=True,
    )


def reverse_migration(apps, schema_editor):
    """Hairudishi data ya kale."""
    ReservationRate = apps.get_model("reservation_rates", "ReservationRate")
    ReservationRate.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("reservation_rates", "0001_initial"),
    ]

    operations = [
        # ═══════════════════════════════════════════════════════
        # 1. Futa fields za kale
        # ═══════════════════════════════════════════════════════
        migrations.RemoveField(model_name="reservationrate", name="fee"),
        migrations.RemoveField(model_name="reservationrate", name="hours"),
        migrations.RemoveField(model_name="reservationrate", name="label_en"),
        migrations.RemoveField(model_name="reservationrate", name="label_sw"),
        migrations.RemoveField(model_name="reservationrate", name="ordering"),
        migrations.RemoveField(model_name="reservationrate", name="sub_en"),
        migrations.RemoveField(model_name="reservationrate", name="sub_sw"),
        migrations.RemoveField(model_name="reservationrate", name="tier"),

        # ═══════════════════════════════════════════════════════
        # 2. Ongeza fields mpya
        # ═══════════════════════════════════════════════════════
        migrations.AddField(
            model_name="reservationrate",
            name="days",
            field=models.PositiveIntegerField(
                default=3,
                help_text="Idadi ya siku reservation inadumu.",
            ),
        ),
        migrations.AddField(
            model_name="reservationrate",
            name="flat_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("50000"),
                help_text="Flat fee ya reservation kwa TZS.",
                max_digits=15,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="reservationrate",
            name="is_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Kama False, reservation ni bure.",
            ),
        ),
        migrations.AddField(
            model_name="reservationrate",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),

        # ═══════════════════════════════════════════════════════
        # 3. Futa data ya kale NA unda singleton mpya
        # ═══════════════════════════════════════════════════════
        migrations.RunPython(
            forward_migration,
            reverse_migration,
        ),

        # ═══════════════════════════════════════════════════════
        # 4. Rename table
        # ═══════════════════════════════════════════════════════
        migrations.AlterModelTable(
            name="reservationrate",
            table="reservation_rate_config",
        ),

        # ═══════════════════════════════════════════════════════
        # 5. Meta options
        # ═══════════════════════════════════════════════════════
        migrations.AlterModelOptions(
            name="reservationrate",
            options={
                "verbose_name": "Ada ya Reservation",
                "verbose_name_plural": "Ada ya Reservation",
            },
        ),
    ]