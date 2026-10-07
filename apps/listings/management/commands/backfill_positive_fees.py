"""
Ensure every listing has a positive fee and every category has a
positive fee rule. Run this once after deploying the "always charge"
change.

Usage:
    python manage.py backfill_positive_fees
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.categories.models import Category
from apps.listings.models import Listing, ListingFee, ListingFeeRule
from apps.listings.services.listing_fee import create_listing_fee


DEFAULT_FLAT = Decimal("3000.00")


class Command(BaseCommand):
    help = "Force every category to have a positive rule and every listing a positive fee."

    def handle(self, *args, **options):
        # 1. Fix zero-value category rules
        zero_rules = ListingFeeRule.objects.filter(is_deleted=False).filter(
            models_Q_zero_rule()
        ) if False else ListingFeeRule.objects.filter(is_deleted=False)

        fixed_rules = 0
        for rule in ListingFeeRule.objects.filter(is_deleted=False):
            flat = Decimal(str(rule.flat_fee or 0))
            pct = Decimal(str(rule.percentage or 0))
            is_flat = (rule.fee_mode or "").upper() == "FLAT"

            if is_flat and flat <= 0:
                rule.flat_fee = DEFAULT_FLAT
                rule.save(update_fields=["flat_fee", "updated_at"])
                fixed_rules += 1
                self.stdout.write(f"  ↻ rule for {rule.category_slug or rule.name} → {DEFAULT_FLAT}")
            elif not is_flat and pct <= 0:
                rule.percentage = Decimal("1.00")
                rule.percentage = Decimal("1.00")
                rule.save(update_fields=["percentage", "updated_at"])
                fixed_rules += 1
                self.stdout.write(f"  ↻ rule for {rule.category_slug or rule.name} → 1.00%")

        # 2. Ensure every category has an active rule
        created_rules = 0
        for cat in Category.objects.filter(is_deleted=False):
            existing = ListingFeeRule.objects.filter(
                category=cat, is_active=True, is_deleted=False,
            ).first()
            if existing:
                continue
            ListingFeeRule.objects.create(
                category=cat,
                category_slug=cat.slug,
                name=cat.name,
                fee_mode="FLAT",
                flat_fee=DEFAULT_FLAT,
                percentage=0,
                min_price=0,
                is_active=True,
                priority=9999,
            )
            created_rules += 1
            self.stdout.write(f"  + rule for {cat.slug} → {DEFAULT_FLAT}")

        # 3. Fix listings with 0 fee
        fixed_fees = 0
        for fee in ListingFee.objects.filter(amount__lte=0):
            try:
                create_listing_fee(fee.listing, force_recompute=True)
                fixed_fees += 1
                self.stdout.write(f"  ↻ listing #{fee.listing_id} fee → {DEFAULT_FLAT}")
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ listing #{fee.listing_id}: {exc}"
                ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. rules_fixed={fixed_rules} rules_created={created_rules} "
            f"fees_fixed={fixed_fees}"
        ))


def models_Q_zero_rule():
    return None  # placeholder
