"""
Idempotent seeder: guarantees every category has an active fee rule.

Runs automatically on every deploy via entrypoint.sh.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.categories.models import Category
from apps.listings.models import ListingFeeRule


CATEGORY_SEEDS = [
    ("nyumba-majengo",          "Nyumba & Majengo",          5000),
    ("viwanja-mashamba",        "Viwanja & Mashamba",        3000),
    ("magari",                  "Magari",                    5000),
    ("biashara-zinazouzwa",     "Biashara Zinazouzwa",      10000),
    ("mashine-heavy-equipment", "Mashine & Heavy Equipment", 7000),
    ("vifaa-vizito",            "Vifaa Vizito",              7000),
    ("pikipiki",                "Pikipiki",                  3000),
    ("mabasi",                  "Mabasi",                    7000),
    ("samani",                  "Samani",                    3000),
    ("vifaa-vya-elektroniki",   "Vifaa vya Elektroniki",     3000),
    ("mifugo",                  "Mifugo",                    3000),
    ("vifaa-vya-nyumbani",      "Vifaa vya Nyumbani",        3000),
    ("fashion",                 "Fashion",                   2000),
    ("jobs",                    "Ajira",                     2000),
    ("huduma",                  "Huduma",                    2000),
    ("mali-nyinginezo",         "Mali Nyinginezo",           2000),
]


class Command(BaseCommand):
    help = "Ensure every category exists and has an active fee rule."

    def handle(self, *args, **options):
        cats_created = rules_created = rules_skipped = 0

        for slug, name, amount in CATEGORY_SEEDS:
            cat, cat_created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "is_active": True},
            )
            if cat_created:
                cats_created += 1
                self.stdout.write("  + category {} ({})".format(slug, name))

            existing = ListingFeeRule.all_objects.filter(
                category=cat, is_deleted=False,
            ).first()

            if existing:
                if not existing.category_slug:
                    existing.category_slug = cat.slug
                    existing.save(update_fields=["category_slug"])
                rules_skipped += 1
                continue

            ListingFeeRule.objects.create(
                category=cat,
                category_slug=cat.slug,
                name=cat.name,
                fee_mode="FLAT",
                flat_fee=Decimal(amount),
                percentage=0,
                min_price=0,
                is_active=True,
                priority=0,
            )
            rules_created += 1
            self.stdout.write("  + rule {} -> TZS {}".format(slug, amount))

        # Any other category without a rule gets a default
        for cat in Category.objects.filter(is_deleted=False):
            if ListingFeeRule.all_objects.filter(
                category=cat, is_deleted=False,
            ).exists():
                continue
            ListingFeeRule.objects.create(
                category=cat,
                category_slug=cat.slug,
                name=cat.name,
                fee_mode="FLAT",
                flat_fee=Decimal(3000),
                percentage=0,
                min_price=0,
                is_active=True,
                priority=9999,
            )
            rules_created += 1
            self.stdout.write(
                "  + default rule {} -> TZS 3000".format(cat.slug)
            )

        self.stdout.write(self.style.SUCCESS(
            "Done. categories_created={} rules_created={} rules_kept={}".format(
                cats_created, rules_created, rules_skipped,
            )
        ))
