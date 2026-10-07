# apps/listings/services/listing_fee.py
"""
Listing fee computation + persistence.

Key rules:
  - Never auto-charge when a category has no configured rule
    (unless settings.LISTING_FEE_ALLOW_FALLBACK is explicitly True).
  - Freeze the quoted amount once a real rule is attached; allow
    re-pricing when the previous computation used a fallback, or
    when the caller asks for a forced refresh (24h staleness).
"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError

from ..models import ListingFee, ListingFeeRule


DEFAULT_FLAT_FEE = Decimal("3000.00")


class ListingFeeNotConfigured(ValidationError):
    """Raised when a category has no fee rule and fallback is disabled."""

    def __init__(self, category_slug=None):
        slug = category_slug or "—"
        super().__init__({
            "detail": (
                "Ada ya kuchapisha haijasanidiwa kwa kundi hili bado. "
                "Tafadhali wasiliana na msimamizi kabla ya kuendelea."
            ),
            "code": "listing_fee_not_configured",
            "category_slug": slug,
        })


def _fallback_allowed():
    return getattr(settings, "LISTING_FEE_ALLOW_FALLBACK", False)


# ============================================================
# RULE LOOKUP
# ============================================================

def get_listing_fee_rule(category_slug=None, price=None, category=None):
    """
    Find the active fee rule for a listing.

    Lookup priority:
      1. FK match on `category`
      2. Slug match on `category_slug`
      3. Legacy match on `name`
      4. Fallback (only if LISTING_FEE_ALLOW_FALLBACK is True)

    Raises ListingFeeNotConfigured when no rule is found and fallback
    is disabled.
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

    # 3. Legacy name match
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

    # 4. No rule found
    if not _fallback_allowed():
        raise ListingFeeNotConfigured(
            category_slug=category_slug
            or (category.slug if category is not None else None)
        )

    # Fallback: auto-create a per-category default
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

    raise ListingFeeNotConfigured()


# ============================================================
# FEE COMPUTATION
# ============================================================

def calculate_listing_fee(price, category_slug=None, category=None):
    """
    Compute the listing fee for a given price and category.

    Returns a dict: { rule, price, percentage, fee_amount }
    Raises ListingFeeNotConfigured if no rule is available.
    """
    price = Decimal(str(price or 0))

    if price <= 0:
        raise ValidationError(
            "Bei ya tangazo lazima iwe kubwa kuliko sifuri."
        )

    rule = get_listing_fee_rule(
        category_slug=category_slug,
        price=price,
        category=category,
    )

    if rule.fee_mode == "FLAT":
        fee_amount = Decimal(str(rule.flat_fee or 0))
    else:
        fee_amount = (
            price * Decimal(str(rule.percentage or 0)) / Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "rule": rule,
        "price": price,
        "percentage": rule.percentage,
        "fee_amount": fee_amount,
    }


# ============================================================
# PERSISTENCE
# ============================================================

def create_listing_fee(listing, *, force_recompute=False):
    """
    Create or refresh the pending listing fee for a listing.

    Freeze semantics:
      - PENDING fee WITH a real `rule` → freeze (seller saw this price).
      - PENDING fee WITHOUT a rule (fallback) → allow recompute.
      - PAID fee → never touched.
      - force_recompute=True → always recompute (stale-fee refresh).
    """
    category_obj = listing.category if listing.category_id else None
    category_slug = getattr(category_obj, "slug", None)

    result = calculate_listing_fee(
        listing.price,
        category_slug=category_slug,
        category=category_obj,
    )

    existing = ListingFee.objects.filter(listing=listing).first()

    if existing is None:
        return ListingFee.objects.create(
            listing=listing,
            seller=listing.seller,
            amount=result["fee_amount"],
            rule=result["rule"],
            percentage=result["percentage"],
            payment_status=ListingFee.PaymentStatus.PENDING,
        )

    # Already paid — never touch
    if existing.payment_status == ListingFee.PaymentStatus.PAID:
        return existing

    # Frozen snapshot with a real rule and no forced refresh → keep it
    if existing.rule_id is not None and not force_recompute:
        return existing

    # Recompute (fallback rule, or force_recompute)
    existing.seller = listing.seller
    existing.amount = result["fee_amount"]
    existing.rule = result["rule"]
    existing.percentage = result["percentage"]
    existing.save(update_fields=[
        "seller", "amount", "rule", "percentage", "updated_at",
    ])
    return existing
