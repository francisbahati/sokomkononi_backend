"""
Print the exact JSON that the frontend receives for the latest listing.
Run this in production to compare with what the browser shows.

Usage:
    python manage.py peek_api
    python manage.py peek_api --id 42
"""
import json

from django.core.management.base import BaseCommand

from apps.listings.models import Listing
from apps.listings.serializers import ListingDetailSerializer


class Command(BaseCommand):
    help = "Dump the exact API response for a listing."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, default=None)

    def handle(self, *args, **options):
        if options["id"]:
            listing = Listing.objects.filter(pk=options["id"]).first()
        else:
            listing = Listing.objects.order_by("-created_at").first()

        if not listing:
            self.stdout.write(self.style.ERROR(
                "No listings in this database. Create one from the frontend first."
            ))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f" LISTING #{listing.pk} :: {listing.title}")
        self.stdout.write("=" * 70)
        self.stdout.write(f" status       : {listing.status}")
        self.stdout.write(f" category     : {getattr(listing.category, 'slug', '—')}")
        self.stdout.write(f" price        : {listing.price}")
        self.stdout.write("")

        # Serialize exactly as the API would
        data = ListingDetailSerializer(listing).data

        self.stdout.write("FEE FIELDS (what the frontend can read):")
        self.stdout.write(f"  fee_required : {data.get('fee_required')}")
        self.stdout.write(f"  fee_amount   : {data.get('fee_amount')}")
        self.stdout.write(f"  fee_status   : {data.get('fee_status')}")
        self.stdout.write(f"  fee_currency : {data.get('fee_currency')}")
        self.stdout.write("")

        self.stdout.write("PAYMENT BLOCK (if present):")
        payment = data.get("payment")
        if payment:
            self.stdout.write(json.dumps(payment, indent=2, default=str))
        else:
            self.stdout.write("  (no payment block in response)")
        self.stdout.write("")

        # Fee row state
        fee = getattr(listing, "listing_fee", None)
        if fee:
            self.stdout.write("FEE ROW IN DB:")
            self.stdout.write(f"  id                : {fee.pk}")
            self.stdout.write(f"  amount            : {fee.amount}")
            self.stdout.write(f"  amount_display    : TZS {fee.amount:,.0f}")
            self.stdout.write(f"  payment_status    : {fee.payment_status}")
            self.stdout.write(f"  rule              : {fee.rule}")
            self.stdout.write(f"  payment_reference : {fee.payment_reference or '—'}")
        else:
            self.stdout.write(self.style.WARNING(
                "NO FEE ROW IN DB — the fee will be computed on demand."
            ))

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(" WHAT THE FRONTEND SHOULD RENDER")
        self.stdout.write("=" * 70)
        if fee:
            self.stdout.write(f"  Ada ya Kuchapisha    TZS {fee.amount:,.0f}")
        elif data.get("fee_amount"):
            self.stdout.write(
                f"  Ada ya Kuchapisha    TZS {data['fee_amount']}"
            )
        else:
            self.stdout.write(self.style.ERROR(
                "  Ada ya Kuchapisha    (missing — frontend shows Inahesabiwa)"
            ))
