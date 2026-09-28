from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.payments.fimipay import create_order

from ..models import Listing, ListingFee


@transaction.atomic
def initiate_listing_fee_payment(*, listing, user):
    listing = (
        Listing.objects
        .select_for_update(of=("self",))
        .select_related("seller", "category")
        .get(pk=listing.pk)
    )
    if listing.seller_id != user.id:
        raise ValidationError("Huruhusiwi kulipia ada ya tangazo hili.")
    if listing.status != Listing.Status.DRAFT:
        raise ValidationError("Ada inaweza kulipwa tu kwa tangazo lenye hali ya DRAFT.")

    try:
        listing_fee = ListingFee.objects.select_for_update().get(listing=listing)
    except ListingFee.DoesNotExist:
        raise ValidationError("Ada ya tangazo haijatengenezwa bado.")

    if listing_fee.payment_status == ListingFee.PaymentStatus.PAID:
        raise ValidationError("Ada ya tangazo hili tayari imelipwa.")

    # ---- Reuse an existing FimiPay order if we already created one ----
    from apps.payments.fimipay import get_order_status

    existing_ref = (listing_fee.payment_reference or "").strip()
    if existing_ref:
        try:
            status_data = get_order_status(existing_ref)
            ps = (status_data.get("payment_status") or "").upper()
            if ps in ("PENDING", "INPROGRESS"):
                # Order still alive at FimiPay — return the same reference so
                # the frontend continues polling instead of re-creating.
                return status_data
            if ps == "SUCCESS":
                # Already paid — nothing to do here (webhook will have fired).
                return status_data
        except Exception:
            # If we can't fetch the old order, fall through and create a new one.
            pass

    order_id = f"LSF-{listing.id}"
    data = create_order(
        order_id=order_id,
        amount=listing_fee.amount,
        buyer_phone=user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method="mobile",
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

    listing_fee.payment_status = ListingFee.PaymentStatus.PAID
    listing_fee.payment_reference = payment_reference or listing_fee.payment_reference
    listing_fee.paid_at = timezone.now()
    listing_fee.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])
    Listing.objects.filter(pk=ref_id).update(
        status=Listing.Status.PENDING_APPROVAL,
        updated_at=timezone.now(),
    )
    return listing_fee
