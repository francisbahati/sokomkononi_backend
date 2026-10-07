"""
Create ListingFee rows for existing listings that don't have one.

Usage:
    python manage.py backfill_listing_fees
    python manage.py backfill_listing_fees --include-drafts
"""
from django.core.management.base import BaseCommand

from apps.listings.models import Listing, ListingFee
from apps.listings.services.listing_fee import (
    ListingFeeNotConfigured,
    create_listing_fee,
)


class Command(BaseCommand):
    help = "Backfill ListingFee rows for listings that lack one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Also process DRAFT listings (default: only live/pending).",
        )

    def handle(self, *args, **options):
        qs = Listing.objects.filter(listing_fee__isnull=True)
        if not options["include_drafts"]:
            qs = qs.exclude(status=Listing.Status.DRAFT)
        qs = qs.exclude(status=Listing.Status.ARCHIVED)

        total = qs.count()
        if total == 0:
            self.stdout.write("All listings have a fee row. Nothing to do.")
            return

        self.stdout.write(f"Backfilling {total} listing(s)...")
        created = skipped = failed = 0

        for listing in qs.iterator():
            try:
                fee = create_listing_fee(listing)
                created += 1
                self.stdout.write(
                    f"  + {listing.pk}  {listing.title[:40]}  → TZS {fee.amount}"
                )
            except ListingFeeNotConfigured:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  ⏭  {listing.pk}  {listing.title[:40]}  → no rule for category"
                ))
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {listing.pk}  {listing.title[:40]}  → {exc}"
                ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created} skipped={skipped} failed={failed}"
        ))
