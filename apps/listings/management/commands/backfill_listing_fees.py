"""
For every listing that's missing a ListingFee row, compute and create
one from the current rule.

Usage:
    python manage.py backfill_listing_fees
"""
from django.core.management.base import BaseCommand

from apps.listings.models import Listing, ListingFee
from apps.listings.services.listing_fee import create_listing_fee


class Command(BaseCommand):
    help = "Create ListingFee rows for listings that don't have one."

    def handle(self, *args, **options):
        listings = Listing.objects.filter(
            listing_fee__isnull=True,
        ).exclude(status=Listing.Status.ARCHIVED)

        total = listings.count()
        if total == 0:
            self.stdout.write("All listings have a fee row. Nothing to do.")
            return

        self.stdout.write(f"Backfilling {total} listing(s)...")
        created = skipped = failed = 0

        for listing in listings.iterator():
            try:
                fee = create_listing_fee(listing)
                created += 1
                self.stdout.write(
                    f"  + {listing.pk} {listing.title[:40]}  "
                    f"→ TZS {fee.amount}"
                )
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {listing.pk}  {listing.title[:40]}  → {exc}"
                ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created} skipped={skipped} failed={failed}"
        ))
