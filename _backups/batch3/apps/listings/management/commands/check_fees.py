"""
Verify every category has a fee rule, and every PENDING listing has a fee row.

Usage:
    python manage.py check_fees
"""
from django.core.management.base import BaseCommand

from apps.categories.models import Category
from apps.listings.models import Listing, ListingFee, ListingFeeRule


class Command(BaseCommand):
    help = "Diagnose listing fee configuration."

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(" CATEGORY FEE RULES")
        self.stdout.write("=" * 70)
        self.stdout.write(f"{'Slug':<30} {'Flat Fee':>12} {'Mode':<12} {'Active':<8}")
        self.stdout.write("-" * 70)

        missing_rules = []
        for cat in Category.objects.filter(is_deleted=False).order_by("slug"):
            rule = ListingFeeRule.objects.filter(
                category=cat, is_active=True, is_deleted=False,
            ).first()
            if rule:
                self.stdout.write(
                    f"{cat.slug:<30} {str(rule.flat_fee):>12} "
                    f"{rule.fee_mode:<12} {'YES':<8}"
                )
            else:
                missing_rules.append(cat.slug)
                self.stdout.write(self.style.WARNING(
                    f"{cat.slug:<30} {'—':>12} {'—':<12} {'MISSING':<8}"
                ))

        self.stdout.write("")
        if missing_rules:
            self.stdout.write(self.style.WARNING(
                f"⚠ {len(missing_rules)} categories have NO fee rule:"
            ))
            for slug in missing_rules:
                self.stdout.write(f"    - {slug}")
            self.stdout.write("")
            self.stdout.write("Fix with:")
            self.stdout.write("  python manage.py seed_all_fee_rules")
        else:
            self.stdout.write(self.style.SUCCESS(
                "✓ All categories have a fee rule"
            ))

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(" LISTINGS MISSING A FEE ROW")
        self.stdout.write("=" * 70)

        no_fee = Listing.objects.filter(listing_fee__isnull=True).exclude(
            status__in=[Listing.Status.ARCHIVED],
        )

        if not no_fee.exists():
            self.stdout.write(self.style.SUCCESS(
                "✓ Every listing has a fee row"
            ))
            return

        self.stdout.write(f"⚠ {no_fee.count()} listing(s) without a fee row:")
        for l in no_fee[:30]:
            self.stdout.write(
                f"    id={l.id} status={l.status} cat={getattr(l.category, 'slug', '—')} "
                f"title={(l.title or '')[:40]}"
            )
        self.stdout.write("")
        self.stdout.write("Fix with:")
        self.stdout.write("  python manage.py backfill_listing_fees")
