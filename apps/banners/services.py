# apps/banners/services.py
"""
Banner ad creation + activation.
Inatumia `AdvertisementPackage` kwa bei na muda.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing

from .models import BannerAd


@transaction.atomic
def create_banner_ad(*, listing_id, seller, package, payment_reference=""):
    """
    Unda PENDING banner ad. Hai-activate listing bado — inasubiri malipo.
    """
    if not package or not package.is_active:
        raise ValidationError({"package": "Advertisement package haipo active."})

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

    existing = BannerAd.objects.filter(
        listing=listing,
        active=True,
        expires_at__gt=timezone.now(),
    ).exists()
    if existing:
        raise ValidationError(
            {"listing": "Tangazo hili tayari lina banner inayotumika."}
        )

    now = timezone.now()
    banner = BannerAd.objects.create(
        listing=listing,
        seller=seller,
        package=package,
        listing_title=listing.title,
        category=getattr(listing.category, "slug", "") or "",
        location=listing.location or "",
        price=listing.price,
        seller_name=seller.name,
        amount=package.price,
        payment_reference=(payment_reference or "").strip() or None,
        active=False,
        payment_status="PENDING",
        expires_at=now + timedelta(hours=package.duration_hours),
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
    hours = banner.package.duration_hours if banner.package else 168
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

    from apps.payments.fimipay import get_order_status as _fp_get_status

    existing_ref = (banner.payment_reference or "").strip()
    if existing_ref:
        try:
            sd = _fp_get_status(existing_ref)
            if (sd.get("payment_status") or "").upper() in ("PENDING", "INPROGRESS", "SUCCESS"):
                return sd
        except Exception:
            pass

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

    hours = banner.package.duration_hours if banner.package else 168
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