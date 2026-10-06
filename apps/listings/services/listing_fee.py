# apps/listings/services/listing_fee.py
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from ..models import ListingFee, ListingFeeRule


DEFAULT_FLAT_FEE = 3000


def get_listing_fee_rule(category_slug=None, price=None, category=None):
    """
    Return the active fee rule for a listing.

    Priority:
      1. FK match on `category`
      2. Slug match on `category_slug`
      3. Legacy name match
      4. Auto-create a per-category default (never returns None)
    """
    # 1. FK match (authoritative)
    if category is not None:
        rule = (
            ListingFeeRule.objects
            .filter(category=category, is_active=True, is_deleted=False)
            .order_by("priority")
            .first()
        )
        if rule:
            return rule

    # 2. Slug match
    if category_slug:
        rule = (
            ListingFeeRule.objects
            .filter(
                category_slug=category_slug,
                is_active=True,
                is_deleted=False,
            )
            .order_by("priority")
            .first()
        )
        if rule:
            if category is not None and not rule.category_id:
                rule.category = category
                rule.save(update_fields=["category"])
            return rule

    # 3. Match by rule.name == category_slug (legacy)
    if category_slug:
        rule = (
            ListingFeeRule.objects
            .filter(
                name__iexact=category_slug,
                is_active=True,
                is_deleted=False,
            )
            .order_by("priority")
            .first()
        )
        if rule:
            return rule

    # 4. Auto-create for this exact category
    if category is not None:
        rule, _ = ListingFeeRule.objects.get_or_create(
            category=category,
            defaults={
                "name": category.name,
                "category_slug": category.slug,
                "fee_mode": "FLAT",
                "flat_fee": DEFAULT_FLAT_FEE,
                "percentage": 0,
                "min_price": 0,
                "is_active": True,
                "priority": 9999,
            },
        )
        return rule

    # 5. Slug-only fallback (no Category object)
    if category_slug:
        rule, _ = ListingFeeRule.objects.get_or_create(
            category_slug=category_slug,
            defaults={
                "name": category_slug,
                "fee_mode": "FLAT",
                "flat_fee": DEFAULT_FLAT_FEE,
                "percentage": 0,
                "is_active": True,
                "priority": 9999,
            },
        )
        return rule

    return None


def calculate_listing_fee(price, category_slug=None, category=None):
    """
    Compute the listing fee.

    FLAT mode        → rule.flat_fee
    PERCENTAGE mode  → price × percentage / 100
    """
    price = Decimal(price or 0)

    if price <= 0:
        raise ValidationError(
            "Bei ya tangazo lazima iwe kubwa kuliko sifuri."
        )

    rule = get_listing_fee_rule(
        category_slug=category_slug,
        price=price,
        category=category,
    )
    if not rule:
        raise ValidationError(
            "Hakuna kanuni ya ada inayolingana na category hii. "
            "Wasiliana na admin ili kuweka fee rule."
        )

    if rule.fee_mode == "FLAT":
        fee_amount = Decimal(rule.flat_fee or 0)
    else:
        fee_amount = (
            price * Decimal(rule.percentage or 0) / Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "rule": rule,
        "price": price,
        "percentage": rule.percentage,
        "fee_amount": fee_amount,
    }


def create_listing_fee(listing):
    """
    Create or update the pending listing fee for a listing.
    """
    category_obj = listing.category if listing.category_id else None
    category_slug = getattr(category_obj, "slug", None)

    result = calculate_listing_fee(
        listing.price,
        category_slug=category_slug,
        category=category_obj,
    )

    listing_fee, created = ListingFee.objects.get_or_create(
        listing=listing,
        defaults={
            "seller": listing.seller,
            "amount": result["fee_amount"],
            "rule": result["rule"],
            "percentage": result["percentage"],
            "payment_status": ListingFee.PaymentStatus.PENDING,
        },
    )

    if not created:
        # Freeze the quoted amount — do NOT recompute on subsequent
        # calls. The user saw this number in the pay dialog.
        return listing_fee

    return listing_fee
