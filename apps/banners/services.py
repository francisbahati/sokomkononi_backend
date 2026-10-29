# apps/banners/services.py
"""
Banner ad creation + activation + campaign pricing.
Inatumia `AdvertisementPackage` kwa bei na muda, au default (168h = siku 7)
kama advertisement fee imezimwa (package=None).
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing

from .models import BannerAd, Campaign


ZERO = Decimal("0.00")
DEFAULT_BANNER_HOURS = 168  # siku 7 — default kama package=None


def _round(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _advertisement_fee_enabled():
    """True kama advertisement fee inatumika; False kama ni bure."""
    try:
        from apps.advertisement_fees.models import AdvertisementFeeConfig
        cfg = AdvertisementFeeConfig.get_solo()
        return bool(cfg and cfg.is_enabled)
    except Exception:
        # Fail-closed: kama lookup inashindwa, chukulia fee inatumika
        return True


# ============================================================================
# BANNER AD
# ============================================================================

@transaction.atomic
def create_banner_ad(*, listing_id, seller, package, payment_reference=""):
    """
    Unda PENDING banner ad. Hai-activate listing bado — inasubiri malipo.

    `package` inaweza kuwa None kama advertisement fee imezimwa.
    """
    fee_enabled = _advertisement_fee_enabled()

    if fee_enabled:
        if not package or not package.is_active:
            raise ValidationError({"package": "Advertisement package haipo active."})
    else:
        # Free mode: package hiari. Kama package imetolewa lakini si active,
        # tunaichukulia kama None.
        if package is not None and not package.is_active:
            package = None

    try:
        listing = Listing.objects.select_for_update().get(pk=listing_id)
    except Listing.DoesNotExist:
        raise ValidationError({"listing": "Tangazo halipatikani."})

    if listing.seller_id != seller.id:
        raise ValidationError(
            {"listing": "Huruhusiwi kutangaza tangazo ambalo si lako."}
        )
    if listing.status != Listing.Status.LIVE:
        raise ValidationError({"listing": "Tangazo lazima liwe AVAILABLE."})

    existing = BannerAd.objects.filter(listing=listing).filter(
        models.Q(active=True, expires_at__gt=timezone.now())
        | models.Q(payment_status="PENDING")
    ).exists()
    if existing:
        raise ValidationError({
            "listing": "Tangazo hili tayari lina banner inayotumika au inayosubiri malipo."
        })

    now = timezone.now()

    # Bei na muda: kama package ipo, tumia; kama haipo (fee imezimwa), 0 na 168h.
    if package is not None:
        amount = package.price
        duration_hours = package.duration_hours
    else:
        amount = ZERO
        duration_hours = DEFAULT_BANNER_HOURS

    banner = BannerAd.objects.create(
        listing=listing,
        seller=seller,
        package=package,
        listing_title=listing.title,
        category=getattr(listing.category, "slug", "") or "",
        location=listing.location or "",
        price=listing.price,
        seller_name=seller.name,
        amount=amount,
        payment_reference=(payment_reference or "").strip() or None,
        active=False,
        payment_status="PENDING",
        expires_at=now + timedelta(hours=duration_hours),
    )
    return banner


@transaction.atomic
def mark_banner_paid_and_activate(*, banner, payment_reference):
    """Mark a PENDING banner as PAID and flip it active."""
    if not payment_reference:
        raise ValidationError("Payment reference inahitajika.")
    ref = payment_reference.strip()
    if not ref:
        raise ValidationError("Payment reference haiwezi kuwa tupu.")

    banner = (
        BannerAd.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=banner.pk)
    )

    if banner.payment_status == "PAID":
        if banner.payment_reference == ref:
            return banner
        raise ValidationError("Banner hii tayari imelipiwa.")

    if BannerAd.objects.filter(payment_reference=ref).exclude(pk=banner.pk).exists():
        raise ValidationError("Payment reference hii tayari imetumika.")

    now = timezone.now()
    hours = banner.package.duration_hours if banner.package else DEFAULT_BANNER_HOURS
    banner.payment_status = "PAID"
    banner.payment_reference = ref
    banner.paid_at = now
    banner.active = True
    banner.expires_at = now + timedelta(hours=hours)
    banner.save(update_fields=[
        "payment_status", "payment_reference", "paid_at",
        "active", "expires_at",
    ])
    return banner


# ============================================================================
# FIMIPAY INTEGRATION
# ============================================================================
from apps.payments.order_ids import make_order_id
from apps.payments.fimipay import (
    create_order as _fp_create_order,
    normalize_payment_method as _fp_normalize_method,
)


@transaction.atomic
def initiate_banner_payment(*, banner, user, payment_method='mobile', phone=''):
    if banner.seller_id != user.id:
        raise ValidationError("Huruhusiwi kulipia banner hii.")
    if banner.payment_status == "PAID":
        raise ValidationError("Banner hii tayari imelipiwa.")

    # Kama ni bure (amount=0), hakuna haja ya FimiPay
    if not banner.amount or Decimal(str(banner.amount)) <= ZERO:
        raise ValidationError(
            "Banner hii haina kiasi cha kulipia. Tumia 'free' reference."
        )

    from apps.payments.fimipay import get_order_status as _fp_get_status

    existing_ref = (banner.payment_reference or "").strip()
    if existing_ref:
        sd = None
        try:
            sd = _fp_get_status(existing_ref)
        except Exception:
            sd = None
        if sd:
            ps = (sd.get("payment_status") or "").upper()
            if ps == "SUCCESS":
                mark_banner_paid_from_webhook(
                    ref_id=banner.pk,
                    payment_reference=sd.get("transid") or existing_ref,
                )
                return sd
            if ps in ("PENDING", "INPROGRESS"):
                return sd

    order_id = make_order_id("ADV", banner.pk)
    data = _fp_create_order(
        order_id=order_id,
        amount=banner.amount,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=_fp_normalize_method(payment_method),
    )
    banner.payment_reference = data.get("order_id") or order_id
    banner.save(update_fields=["payment_reference"])
    return data


@transaction.atomic
def mark_banner_paid_from_webhook(*, ref_id, payment_reference):
    banner = BannerAd.objects.select_for_update().get(pk=ref_id)
    if banner.payment_status == "PAID":
        return banner

    ref = (payment_reference or "").strip()
    if not ref:
        raise ValidationError("Payment reference inahitajika.")
    if BannerAd.objects.filter(payment_reference=ref).exclude(pk=banner.pk).exists():
        raise ValidationError("Payment reference hii tayari imetumika.")

    hours = banner.package.duration_hours if banner.package else DEFAULT_BANNER_HOURS
    banner.payment_status = "PAID"
    banner.payment_reference = ref
    banner.paid_at = timezone.now()
    banner.active = True
    banner.expires_at = timezone.now() + timedelta(hours=hours)
    banner.save(update_fields=[
        "payment_status", "payment_reference", "paid_at",
        "active", "expires_at",
    ])
    return banner


# ============================================================================
# CAMPAIGN PRICING
# ============================================================================

def get_active_campaign(applies_to):
    """Return the live campaign, cached for 60s."""
    from django.core.cache import cache
    cache_key = f"active_campaign:{applies_to}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    now = timezone.now()
    campaign = (
        Campaign.objects
        .filter(
            active=True,
            applies_to__in=[applies_to, Campaign.AppliesTo.ALL],
        )
        .filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        )
        .filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        .order_by("-discount_percent")
        .first()
    )
    cache.set(cache_key, campaign or False, 60)
    return campaign


def calculate_promotion_price(base_price, applies_to):
    base_price = Decimal(str(base_price or 0))
    campaign = get_active_campaign(applies_to)

    if campaign and campaign.discount_percent > 0:
        pct = Decimal(str(campaign.discount_percent))
        discount_amount = _round(base_price * pct / Decimal("100"))
        final_price = base_price - discount_amount
        if final_price < ZERO:
            final_price = ZERO
        return {
            "base_price": _round(base_price),
            "discount_percent": pct,
            "discount_amount": _round(discount_amount),
            "final_price": _round(final_price),
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "campaign_end_date": campaign.end_date,
        }

    return {
        "base_price": _round(base_price),
        "discount_percent": ZERO,
        "discount_amount": ZERO,
        "final_price": _round(base_price),
        "campaign_id": None,
        "campaign_name": None,
        "campaign_end_date": None,
    }


@transaction.atomic
def mark_banner_as_refunded(*, ref_id, reason=""):
    banner = BannerAd.objects.select_for_update().get(pk=ref_id)
    if banner.payment_status == "REFUNDED":
        return banner
    banner.payment_status = "REFUNDED"
    banner.active = False
    banner.save(update_fields=["payment_status", "active"])
    return banner