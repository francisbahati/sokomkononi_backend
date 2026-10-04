from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from ..models import ListingFee, ListingFeeRule


def get_listing_fee_rule(category_slug=None, price=None, category=None):
    """
    Tafuta fee rule kwa category.

    Kila category ina rule MOJA ya FLAT fee (fee haitofautiani na bei).
    Rule inatafutwa kwa `name` ambayo inalingana na `category_slug`.

    Fallback (legacy): tafuta kwa bei (min_price/max_price).
    """
    # 1a. Tafuta kwa category_slug field (primary, new)
    if category_slug:
        rule = (
            ListingFeeRule.objects
            .filter(
                is_active=True,
                is_deleted=False,
                category_slug=category_slug,
            )
            .order_by("priority")
            .first()
        )
        if rule:
            return rule

    # 1b. Fallback: match by name (legacy behavior)
    if category_slug:
        rule = (
            ListingFeeRule.objects
            .filter(
                is_active=True,
                is_deleted=False,
                name__iexact=category_slug,
            )
            .order_by("priority")
            .first()
        )
        if rule:
            return rule

    # 2. Fallback: rule yoyote active yenye FLAT mode (kama category haipo)
    if category_slug:
        rule = (
            ListingFeeRule.objects
            .filter(
                is_active=True,
                is_deleted=False,
                fee_mode="FLAT",
            )
            .order_by("priority")
            .first()
        )
        if rule:
            return rule

    # 3. Fallback: any active FLAT rule (system-wide default)
    rule = (
        ListingFeeRule.objects
        .filter(is_active=True, is_deleted=False, fee_mode="FLAT")
        .order_by("priority", "min_price")
        .first()
    )
    if rule:
        return rule

    # 4. Fallback: tafuta kwa bei (legacy)
    if price is not None:
        price_dec = Decimal(price)
        rules = ListingFeeRule.objects.filter(
            is_active=True,
            is_deleted=False,
            min_price__lte=price_dec,
        ).order_by("priority", "min_price")
        for rule in rules:
            if rule.max_price is None or price_dec <= rule.max_price:
                return rule

    # 5. Last resort: auto-create a system default rule so listings
    #    NEVER fail to get a fee. Admins can edit it later.
    default_rule, _ = ListingFeeRule.objects.get_or_create(
        category_slug="__default__",
        defaults={
            "name": "Default Listing Fee",
            "fee_mode": "FLAT",
            "flat_fee": 5000,
            "percentage": 0,
            "is_active": True,
            "priority": 9999,
        },
    )
    return default_rule


def calculate_listing_fee(price, category_slug=None, category=None):
    """
    Hesabu listing fee kwa listing.

    Kama category_slug imetolewa, tumia FLAT fee ya category.
    La sivyo, tumia bei (legacy behavior).
    """
    price = Decimal(price)

    if price <= 0:
        raise ValidationError(
            "Bei ya tangazo lazima iwe kubwa kuliko sifuri."
        )

    rule = get_listing_fee_rule(
        category_slug=category_slug, price=price, category=category,
    )
    if not rule:
        raise ValidationError(
            "Hakuna kanuni ya ada inayolingana na category hii. "
            "Wasiliana na admin ili kuweka fee rule."
        )

    # FLAT → tumia flat_fee moja kwa moja
    if rule.fee_mode == "FLAT":
        fee_amount = Decimal(rule.flat_fee)
    else:
        # PERCENTAGE (legacy)
        fee_amount = (
            price * rule.percentage / Decimal("100")
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
        if listing_fee.payment_status == ListingFee.PaymentStatus.PAID:
            return listing_fee

        listing_fee.seller = listing.seller
        listing_fee.amount = result["fee_amount"]
        listing_fee.rule = result["rule"]
        listing_fee.percentage = result["percentage"]
        listing_fee.payment_status = ListingFee.PaymentStatus.PENDING

        listing_fee.save(update_fields=[
            "seller", "amount", "rule", "percentage",
            "payment_status", "updated_at",
        ])

    return listing_fee