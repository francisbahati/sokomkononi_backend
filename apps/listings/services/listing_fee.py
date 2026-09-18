from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from ..models import ListingFee, ListingFeeRule


def get_listing_fee_rule(price):
    price = Decimal(price)

    rules = ListingFeeRule.objects.filter(
        is_active=True,
        min_price__lte=price,
    ).order_by("priority", "min_price")

    for rule in rules:
        if rule.max_price is None or price <= rule.max_price:
            return rule

    return None


def calculate_listing_fee(price):
    price = Decimal(price)

    if price <= 0:
        raise ValidationError(
            "Bei ya tangazo lazima iwe kubwa kuliko sifuri."
        )

    rule = get_listing_fee_rule(price)
    if not rule:
        raise ValidationError(
            "Hakuna kanuni ya ada inayolingana na bei ya tangazo."
        )

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
    Persists the rule and percentage snapshot for audit.
    A paid fee is never overwritten.
    """
    result = calculate_listing_fee(listing.price)

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