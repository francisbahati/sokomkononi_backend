# apps/reservation_rates/migrations/0004_seed_default_tiers.py
from django.db import migrations


DEFAULTS = [
    # (hours, fee, order)
    (12, 1000, 1),
    (24, 2000, 2),
    (36, 3000, 3),
    (48, 4000, 4),
    (72, 5000, 5),
    (96, 6000, 6),
    (168, 10000, 7),  # siku 7
]


def seed_tiers(apps, schema_editor):
    ReservationTier = apps.get_model("reservation_rates", "ReservationTier")
    ReservationSettings = apps.get_model("reservation_rates", "ReservationSettings")

    for hours, fee, order in DEFAULTS:
        ReservationTier.objects.get_or_create(
            hours=hours,
            defaults={
                "fee": fee,
                "order": order,
                "is_active": True,
            },
        )

    # Ensure settings singleton exists
    ReservationSettings.objects.get_or_create(pk=1, defaults={"is_enabled": True})


def unseed_tiers(apps, schema_editor):
    ReservationTier = apps.get_model("reservation_rates", "ReservationTier")
    hours = [h for h, _, _ in DEFAULTS]
    ReservationTier.objects.filter(hours__in=hours).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("reservation_rates", "0003_reservationsettings_reservationtier_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_tiers, unseed_tiers),
    ]