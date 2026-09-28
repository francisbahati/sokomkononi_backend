from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import Listing, ListingFee


@transaction.atomic
def mark_listing_fee_as_paid(listing, payment_reference):
    if not payment_reference:
        raise ValidationError("Payment reference inahitajika.")

    payment_reference = payment_reference.strip()
    if not payment_reference:
        raise ValidationError("Payment reference haiwezi kuwa tupu.")

    listing = (
        Listing.objects
        .select_for_update(of=("self",))
        .select_related("seller", "category")
        .get(pk=listing.pk)
    )

    try:
        listing_fee = (
            ListingFee.objects
            .select_for_update()
            .get(listing=listing)
        )
    except ListingFee.DoesNotExist:
        raise ValidationError("Ada ya tangazo haijatengenezwa bado.")

    if listing.status != Listing.Status.DRAFT:
        raise ValidationError(
            "Ada inaweza kulipwa tu kwa tangazo lenye hali ya DRAFT."
        )

    if listing_fee.payment_status == ListingFee.PaymentStatus.PAID:
        raise ValidationError("Ada ya tangazo hili tayari imelipwa.")

    if ListingFee.objects.filter(
        payment_reference=payment_reference
    ).exclude(pk=listing_fee.pk).exists():
        raise ValidationError("Payment reference hii tayari imetumika.")

    listing_fee.payment_status = ListingFee.PaymentStatus.PAID
    listing_fee.payment_reference = payment_reference
    listing_fee.paid_at = timezone.now()
    listing_fee.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])

    listing.status = Listing.Status.PENDING_APPROVAL
    listing.save(update_fields=["status", "updated_at"])

    return listing_fee
