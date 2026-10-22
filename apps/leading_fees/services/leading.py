# apps/leading_fees/services/leading.py
"""Leading purchase flow. Inatumia package badala ya config."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing

from ..models import LeadingFeeConfig, LeadingPackage, ListingLeading


def _get_config():
    return LeadingFeeConfig.get_solo()


def _validate_seller(listing, user):
    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not user.is_active:
        raise ValidationError("Akaunti yako haipo active.")
    if not user.is_verified:
        raise ValidationError("Akaunti yako lazima iwe imethibitishwa.")
    if listing.seller_id != user.id and not user.is_staff:
        raise ValidationError("Huruhusiwi kupandisha tangazo ambalo si lako.")
    if listing.status != Listing.Status.LIVE:
        raise ValidationError("Tangazo lazima liwe AVAILABLE.")


@transaction.atomic
def create_leading(*, listing_id, user, package, payment_reference=""):
    """Create a PENDING leading purchase. Does NOT touch the listing yet."""
    try:
        listing = Listing.objects.select_for_update(of=("self",)).get(pk=listing_id)
    except Listing.DoesNotExist:
        raise ValidationError({"listing": "Tangazo halipatikani."})

    _validate_seller(listing, user)

    if not package or not package.is_active:
        raise ValidationError({"package": "Leading package haipo active."})

    now = timezone.now()
    leading = ListingLeading.objects.create(
        listing=listing,
        seller=user,
        package=package,
        days=round(package.duration_hours / 24) or 1,
        price=package.price,
        payment_status=ListingLeading.PaymentStatus.PENDING,
        status=ListingLeading.Status.PENDING,
        payment_reference=(payment_reference or "").strip() or None,
        expires_at=None,
    )
    return leading


@transaction.atomic
def mark_leading_paid(*, leading, payment_reference):
    if not payment_reference:
        raise ValidationError("Payment reference inahitajika.")
    ref = payment_reference.strip()
    if not ref:
        raise ValidationError("Payment reference haiwezi kuwa tupu.")

    leading = (
        ListingLeading.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=leading.pk)
    )

    if (leading.payment_status == ListingLeading.PaymentStatus.PAID
            and leading.payment_reference == ref):
        return leading
    if leading.payment_status == ListingLeading.PaymentStatus.PAID:
        raise ValidationError("Leading hii tayari imelipiwa.")
    if leading.status in (ListingLeading.Status.CANCELLED, ListingLeading.Status.EXPIRED):
        raise ValidationError("Leading hii haiwezi kulipiwa.")

    if ListingLeading.objects.filter(payment_reference=ref).exclude(pk=leading.pk).exists():
        raise ValidationError("Payment reference hii tayari imetumika.")

    leading.payment_status = ListingLeading.PaymentStatus.PAID
    leading.payment_reference = ref
    leading.paid_at = timezone.now()
    leading.save(update_fields=["payment_status", "payment_reference", "paid_at", "updated_at"])

    return _activate(leading)


@transaction.atomic
def _activate(leading):
    leading = (
        ListingLeading.objects
        .select_for_update(of=("self",))
        .select_related("listing", "package")
        .get(pk=leading.pk)
    )
    if leading.status == ListingLeading.Status.ACTIVE:
        return leading

    listing = Listing.objects.select_for_update().get(pk=leading.listing_id)
    if listing.status != Listing.Status.LIVE:
        raise ValidationError("Tangazo lazima liwe AVAILABLE wakati leading ina-activate.")

    now = timezone.now()
    base = listing.leading_until if (listing.leading_until and listing.leading_until > now) else now
    hours = leading.package.duration_hours if leading.package else 168
    expires_at = base + timedelta(hours=hours)

    leading.status = ListingLeading.Status.ACTIVE
    leading.starts_at = now
    leading.expires_at = expires_at
    leading.save(update_fields=["status", "starts_at", "expires_at", "updated_at"])

    listing.leading_until = expires_at
    listing.save(update_fields=["leading_until", "updated_at"])

    return leading


@transaction.atomic
@transaction.atomic
def expire_stale_leading():
    now = timezone.now()
    qs = ListingLeading.objects.select_for_update().filter(
        status=ListingLeading.Status.ACTIVE, expires_at__lt=now,
    )
    count = 0
    for leading in qs:
        leading.status = ListingLeading.Status.EXPIRED
        leading.save(update_fields=["status", "updated_at"])
        count += 1

        still_active = ListingLeading.objects.filter(
            listing_id=leading.listing_id,
            status=ListingLeading.Status.ACTIVE,
            expires_at__gt=now,
        ).exists()
        if not still_active:
            Listing.objects.filter(pk=leading.listing_id).update(
                leading_until=None,
            )
    return count


# ============================================================================
# FIMIPAY INTEGRATION
# ============================================================================
from apps.payments.order_ids import make_order_id
from apps.payments.fimipay import (
    create_order as _fp_create_order,
    normalize_payment_method as _fp_normalize_method,
)


@transaction.atomic
def initiate_leading_payment(*, leading, user, payment_method='mobile', phone=''):
    leading = (
        ListingLeading.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=leading.pk)
    )
    if leading.seller_id != user.id:
        raise ValidationError("Huruhusiwi kulipia leading hii.")
    if leading.payment_status == ListingLeading.PaymentStatus.PAID:
        # Bila hii, order mpya ingeundwa na mteja angelipa mara ya pili.
        raise ValidationError("Leading hii tayari imelipiwa.")

    from apps.payments.fimipay import get_order_status as _fp_get_status

    existing_ref = (leading.payment_reference or "").strip()
    if existing_ref:
        sd = None
        try:
            sd = _fp_get_status(existing_ref)
        except Exception:
            sd = None
        if sd:
            ps = (sd.get("payment_status") or "").upper()
            if ps == "SUCCESS":
                # Tayari imelipwa FimiPay: itumie sasa (webhook inaweza kuwa
                # imekosa). Errors hapa zinapita juu kwa makusudi — kamwe
                # usiunde order ya pili kwa malipo yaliyokwisha kufanyika.
                mark_leading_paid_from_webhook(
                    ref_id=leading.pk,
                    payment_reference=sd.get("transid") or existing_ref,
                )
                return sd
            if ps in ("PENDING", "INPROGRESS"):
                return sd

    order_id = make_order_id("LDS", leading.pk)
    data = _fp_create_order(
        order_id=order_id,
        amount=leading.price,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=_fp_normalize_method(payment_method),
    )
    leading.payment_reference = data.get("order_id") or order_id
    leading.save(update_fields=["payment_reference", "updated_at"])
    return data


@transaction.atomic
def mark_leading_paid_from_webhook(*, ref_id, payment_reference):
    leading = (
        ListingLeading.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=ref_id)
    )
    if leading.payment_status == ListingLeading.PaymentStatus.PAID:
        return leading

    ref = (payment_reference or "").strip()
    if ref and ListingLeading.objects.filter(payment_reference=ref).exclude(pk=leading.pk).exists():
        raise ValidationError("Payment reference hii tayari imetumika.")

    leading.payment_status = ListingLeading.PaymentStatus.PAID
    leading.payment_reference = payment_reference
    leading.paid_at = timezone.now()
    leading.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])
    return _activate(leading)

@transaction.atomic
def mark_leading_as_refunded(*, ref_id, reason=""):
    leading = ListingLeading.objects.select_for_update().get(pk=ref_id)
    if leading.payment_status == ListingLeading.PaymentStatus.REFUNDED:
        return leading
    leading.payment_status = ListingLeading.PaymentStatus.REFUNDED
    leading.status = ListingLeading.Status.CANCELLED
    leading.save(update_fields=["payment_status", "status", "updated_at"])

    if leading.listing_id:
        now = timezone.now()
        latest_other = (
            ListingLeading.objects
            .filter(
                listing_id=leading.listing_id,
                status=ListingLeading.Status.ACTIVE,
                expires_at__gt=now,
            )
            .exclude(pk=leading.pk)
            .order_by("-expires_at")
            .values_list("expires_at", flat=True)
            .first()
        )
        Listing.objects.filter(pk=leading.listing_id).update(
            leading_until=latest_other,
            updated_at=now,
        )
    return leading