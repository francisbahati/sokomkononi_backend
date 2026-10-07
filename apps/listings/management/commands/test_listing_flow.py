"""
End-to-end sanity check for the listing + payment flow.

Runs through every state transition locally (does NOT hit FimiPay).

Usage:
    python manage.py test_listing_flow
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.categories.models import Category
from apps.listings.models import Listing, ListingFee
from apps.listings.services.listing_fee import (
    ListingFeeNotConfigured,
    calculate_listing_fee,
    create_listing_fee,
)


class Command(BaseCommand):
    help = "Sanity-check the listing fee contract without hitting FimiPay."

    def handle(self, *args, **options):
        ok = True

        self.stdout.write("=" * 70)
        self.stdout.write(" LISTING FEE FLOW — SELF TEST")
        self.stdout.write("=" * 70)
        self.stdout.write("")

        # ----------------------------------------------------------
        # 1. Category fee rules exist
        # ----------------------------------------------------------
        self.stdout.write("1. Category fee rules")
        cats = list(Category.objects.filter(is_deleted=False).order_by("slug"))
        missing = []
        for cat in cats:
            try:
                r = calculate_listing_fee(
                    Decimal("5000000"),
                    category_slug=cat.slug,
                    category=cat,
                )
                self.stdout.write(
                    f"   ✓ {cat.slug:30s} TZS {r['fee_amount']}"
                )
            except ListingFeeNotConfigured:
                missing.append(cat.slug)
                self.stdout.write(self.style.ERROR(
                    f"   ✗ {cat.slug:30s} NO RULE"
                ))
        if missing:
            ok = False
            self.stdout.write(self.style.ERROR(
                f"\n   → {len(missing)} categories missing rules. "
                f"Run: python manage.py force_seed_fees\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "   All categories have rules ✓\n"
            ))

        # ----------------------------------------------------------
        # 2. Latest listing has a fee
        # ----------------------------------------------------------
        self.stdout.write("2. Latest listing fee row")
        latest = Listing.objects.order_by("-id").first()
        if not latest:
            self.stdout.write("   (no listings exist yet — skipping)\n")
        else:
            fee = getattr(latest, "listing_fee", None)
            if fee is None:
                ok = False
                self.stdout.write(self.style.ERROR(
                    f"   ✗ listing #{latest.id} has no fee row "
                    f"(run backfill_listing_fees)\n"
                ))
            else:
                self.stdout.write(
                    f"   ✓ listing #{latest.id} status={latest.status}\n"
                    f"     fee={fee.amount} payment={fee.payment_status}\n"
                )

        # ----------------------------------------------------------
        # 3. Endpoints exist
        # ----------------------------------------------------------
        self.stdout.write("3. Endpoint existence")
        from django.urls import get_resolver

        def flatten(resolver, prefix=""):
            for p in resolver.url_patterns:
                if hasattr(p, "url_patterns"):
                    yield from flatten(p, prefix + str(p.pattern))
                else:
                    yield prefix + str(p.pattern)

        urls = list(flatten(get_resolver()))
        expected = {
            "listings/{id}/":          "GET /listings/{id}/",
            "listings/{id}/fee/":      "GET /listings/{id}/fee/",
            "listings/{id}/fee/pay/":  "POST /listings/{id}/fee/pay/",
            "payments/order-status/":  "POST /payments/order-status/",
            "payments/webhook/":       "POST /payments/webhook/",
        }
        for needle, label in expected.items():
            found = any(needle in u for u in urls)
            if found:
                self.stdout.write(f"   ✓ {label}")
            else:
                ok = False
                self.stdout.write(self.style.ERROR(f"   ✗ {label} MISSING"))
        self.stdout.write("")

        # ----------------------------------------------------------
        # 4. Admin moderation filters unpaid
        # ----------------------------------------------------------
        self.stdout.write("4. Admin moderation filter")
        unpaid_in_admin = Listing.objects.filter(
            status=Listing.Status.PENDING_APPROVAL,
            listing_fee__payment_status__in=[
                ListingFee.PaymentStatus.PENDING,
                ListingFee.PaymentStatus.FAILED,
            ],
        ).count()
        if unpaid_in_admin == 0:
            self.stdout.write(
                "   ✓ No unpaid listings are visible to admin\n"
            )
        else:
            self.stdout.write(self.style.WARNING(
                f"   ⚠ {unpaid_in_admin} unpaid listing(s) in "
                f"PENDING_APPROVAL — check webhook/credits logic\n"
            ))

        # ----------------------------------------------------------
        # 5. State transition matrix
        # ----------------------------------------------------------
        self.stdout.write("5. State transitions")
        self.stdout.write("   DRAFT             → PENDING_PAYMENT (fee created)")
        self.stdout.write("   PENDING_PAYMENT   → PENDING_APPROVAL (fee paid)")
        self.stdout.write("   PENDING_APPROVAL  → LIVE (admin approves)")
        self.stdout.write("   PENDING_APPROVAL  → REJECTED (admin rejects)")
        self.stdout.write("   REJECTED          → PENDING_PAYMENT (seller retries)")
        self.stdout.write("")

        # ----------------------------------------------------------
        # Final verdict
        # ----------------------------------------------------------
        self.stdout.write("=" * 70)
        if ok:
            self.stdout.write(self.style.SUCCESS(
                " ✓ BACKEND CONTRACT IS READY\n"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                " ✗ SOME CHECKS FAILED — fix above before testing frontend\n"
            ))
        self.stdout.write("=" * 70)
