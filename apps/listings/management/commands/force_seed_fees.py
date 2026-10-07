"""
Guarantee every category has an active fee rule.
Existing rules are left untouched (only missing ones are created).

Usage:
    python manage.py force_seed_fees
    python manage.py force_seed_fees --overwrite   # reset all rules to defaults
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.categories.models import Category
from apps.listings.models import ListingFeeRule


# Sensible defaults per known slug. Unknown categories get DEFAULT_FLAT.
KNOWN_FEES = {
    "nyumba-majengo":          Decimal("5000"),
    "viwanja-mashamba":        Decimal("3000"),
    "magari":                  Decimal("5000"),
    "biashara-zinazouzwa":     Decimal("10000"),
    "mashine-heavy-equipment": Decimal("7000"),
    "vifaa-vizito":            Decimal("7000"),
    "pikipiki":                Decimal("3000"),
    "mabasi":                  Decimal("7000"),
    "samani":                  Decimal("3000"),
    "vifaa-vya-elektroniki":   Decimal("3000"),
    "mifugo":                  Decimal("3000"),
    "vifaa-vya-nyumbani":      Decimal("3000"),
    "fashion":                 Decimal("2000"),
    "jobs":                    Decimal("2000"),
    "huduma":                  Decimal("2000"),
    "mali-nyinginezo":         Decimal("2000"),
}
DEFAULT_FLAT = Decimal("3000")


class Command(BaseCommand):
    help = "Guarantee every category has an active fee rule."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Reset ALL rules to defaults (destructive).",
        )

    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        created = updated = skipped = 0

        for cat in Category.objects.filter(is_deleted=False).order_by("slug"):
            fee_amount = KNOWN_FEES.get(cat.slug, DEFAULT_FLAT)

            existing = ListingFeeRule.all_objects.filter(
                category=cat, is_deleted=False,
            ).first()

            if existing:
                if overwrite:
                    existing.flat_fee = fee_amount
                    existing.fee_mode = "FLAT"
                    existing.percentage = 0
                    existing.is_active = True
                    existing.save()
                    updated += 1
                    self.stdout.write(f"  ↻ {cat.slug} → TZS {fee_amount}")
                else:
                    skipped += 1
                    self.stdout.write(f"  = {cat.slug} → TZS {existing.flat_fee} (kept)")
                continue

            ListingFeeRule.objects.create(
                category=cat,
                category_slug=cat.slug,
                name=cat.name,
                fee_mode="FLAT",
                flat_fee=fee_amount,
                percentage=0,
                min_price=0,
                is_active=True,
                priority=0,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(
                f"  + {cat.slug} → TZS {fee_amount}"
            ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created} updated={updated} skipped={skipped}"
        ))
