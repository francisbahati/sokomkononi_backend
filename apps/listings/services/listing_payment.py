# apps/listings/services/listing_payment.py
"""
FimiPay initiation + webhook handling for listing fees.
"""
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.payments.order_ids import make_order_id
from apps.payments.fimipay import (
    create_order,
    normalize_payment_method as _fp_normalize_method,
)

from ..models import Listing, ListingFee


def _reprice_window_hours():
    return getattr(settings, "LISTING_FEE_REPRICE_AFTER_HOURS", 24)


def maybe_reprice_stale_fee(listing_fee, *, listing=None):
    """
    If the fee is PENDING and older than LISTING_FEE_REPRICE_AFTER_HOURS,
    recompute it from the current rule so admin changes take effect on
    abandoned drafts.
    """
    if listing_fee.payment_status != ListingFee.PaymentStatus.PENDING:
        return listing_fee

    age_hours = (
        timezone.now() - listing_fee.created_at
    ).total_seconds() / 3600

    if age_hours < _reprice_window_hours():
        return listing_fee

    listing = listing or listing_fee.listing

    try:
        from .listing_fee import create_listing_fee
        return create_listing_fee(listing, force_recompute=True)
    except Exception:
        # If re-pricing fails, keep the old amount. Logged by caller.
        return listing_fee


@transaction.atomic
def initiate_listing_fee_payment(*, listing, user, payment_method='mobile', phone=''):
    listing = (
        Listing.objects
        .select_for_update(of=("self",))
        .select_related("seller", "category")
        .get(pk=listing.pk)
    )
    if listing.seller_id != user.id:
        raise ValidationError("Huruhusiwi kulipia ada ya tangazo hili.")
    allowed_states = (
        Listing.Status.DRAFT,
        Listing.Status.PENDING_PAYMENT,
        Listing.Status.REJECTED,
    )
    if listing.status not in allowed_states:
        raise ValidationError(
            f"Ada haiwezi kulipwa kwa tangazo lenye hali ya {listing.status}."
        )

    try:
        listing_fee = ListingFee.objects.select_for_update().get(listing=listing)
    except ListingFee.DoesNotExist:
        raise ValidationError("Ada ya tangazo haijatengenezwa bado.")

    if listing_fee.payment_status == ListingFee.PaymentStatus.PAID:
        raise ValidationError("Ada ya tangazo hili tayari imelipwa.")

    # Re-price if stale (abandoned draft)
    listing_fee = maybe_reprice_stale_fee(listing_fee, listing=listing)

    # ---- Reuse an existing FimiPay order if we already created one ----
    from apps.payments.fimipay import get_order_status

    existing_ref = (listing_fee.payment_reference or "").strip()
    if existing_ref:
        try:
            status_data = get_order_status(existing_ref)
            ps = (status_data.get("payment_status") or "").upper()
            if ps in ("PENDING", "INPROGRESS"):
                return status_data
            if ps == "SUCCESS":
                return status_data
        except Exception:
            pass

    order_id = make_order_id("LSF", listing.id)
    data = create_order(
        order_id=order_id,
        amount=listing_fee.amount,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=_fp_normalize_method(payment_method),
    )

    listing_fee.payment_reference = data.get("order_id") or order_id
    listing_fee.save(update_fields=["payment_reference", "updated_at"])
    return data


@transaction.atomic
def mark_listing_fee_as_paid_from_webhook(*, ref_id, payment_reference):
    try:
        listing_fee = (
            ListingFee.objects
            .select_for_update()
            .select_related("listing")
            .get(listing_id=ref_id)
        )
    except ListingFee.DoesNotExist:
        return None

    if listing_fee.payment_status == ListingFee.PaymentStatus.PAID:
        return listing_fee

    ref = (payment_reference or listing_fee.payment_reference or "").strip()
    if ref and ListingFee.objects.filter(
        payment_reference=ref,
    ).exclude(pk=listing_fee.pk).exists():
        # Duplicate transid — suffix so the unique column holds
        ref = f"{ref}-{uuid.uuid4().hex[:8]}"

    listing_fee.payment_status = ListingFee.PaymentStatus.PAID
    listing_fee.payment_reference = ref
    listing_fee.paid_at = timezone.now()
    listing_fee.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])

    # Advance the listing to PENDING_APPROVAL for admin review
    Listing.objects.filter(pk=ref_id).update(
        status=Listing.Status.PENDING_APPROVAL,
        updated_at=timezone.now(),
    )
    return listing_fee
