"""
Seed one ListingFeeRule per category with a sensible flat fee.

Usage:
    python manage.py seed_listing_fee_rules
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.listings.models import ListingFeeRule


DEFAULT_RULES = [
    # (category_slug, label, flat_fee, priority)
    ("nyumba-majengo",          "Nyumba & Majengo",            5000,  1),
    ("viwanja-mashamba",        "Viwanja & Mashamba",          3000,  2),
    ("magari",                  "Magari",                      5000,  3),
    ("biashara-zinazouzwa",     "Biashara Zinazouzwa",        10000,  4),
    ("mashine-heavy-equipment", "Mashine & Heavy Equipment",   7000,  5),
]


class Command(BaseCommand):
    help = "Seed default ListingFeeRule rows for every category."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing rules (default: only create missing ones).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        created = updated = skipped = 0

        for slug, name, flat_fee, priority in DEFAULT_RULES:
            existing = ListingFeeRule.all_objects.filter(
                category_slug=slug, is_deleted=False,
            ).first()

            if existing and not force:
                skipped += 1
                self.stdout.write(f"  ⏭  Skipped (exists): {name}")
                continue

            rule, was_created = ListingFeeRule.objects.update_or_create(
                category_slug=slug,
                defaults={
                    "name": name,
                    "fee_mode": "FLAT",
                    "flat_fee": Decimal(flat_fee),
                    "percentage": 0,
                    "min_price": 0,
                    "max_price": None,
                    "is_active": True,
                    "priority": priority,
                    "is_deleted": False,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Created: {name} → TZS {flat_fee}"
                    )
                )
            else:
                updated += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  🔄 Updated: {name} → TZS {flat_fee}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} skipped={skipped}"
            )
        )
