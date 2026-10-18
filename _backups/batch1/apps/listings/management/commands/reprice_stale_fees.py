"""
Re-price PENDING listing fees older than N hours so admin fee changes
take effect on abandoned drafts.

Usage:
    python manage.py reprice_stale_fees
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.listings.models import ListingFee
from apps.listings.services.listing_payment import maybe_reprice_stale_fee


class Command(BaseCommand):
    help = "Re-price PENDING fees older than LISTING_FEE_REPRICE_AFTER_HOURS."

    def handle(self, *args, **options):
        qs = ListingFee.objects.filter(
            payment_status=ListingFee.PaymentStatus.PENDING,
        ).select_related("listing", "listing__category")

        total = qs.count()
        if total == 0:
            self.stdout.write("No PENDING fees to re-price.")
            return

        changed = unchanged = failed = 0
        for fee in qs.iterator():
            old_amount = fee.amount
            new_fee = maybe_reprice_stale_fee(fee, listing=fee.listing)
            if new_fee.amount != old_amount:
                changed += 1
                self.stdout.write(
                    f"  ↻ {fee.pk}  {fee.listing.title[:40]}  "
                    f"{old_amount} → {new_fee.amount}"
                )
            else:
                unchanged += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. changed={changed} unchanged={unchanged} failed={failed}"
        ))
