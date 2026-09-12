from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import Listing, ListingFee


@transaction.atomic
def mark_listing_fee_as_paid(listing, payment_reference):
    """
    Mark a listing fee as paid and move the listing to
    PENDING_APPROVAL.

    This is currently a payment simulation/service layer.
    A real payment gateway will call this service after
    successful payment confirmation/webhook.
    """

    if not payment_reference:
        raise ValidationError(
            "Payment reference inahitajika."
        )

    payment_reference = payment_reference.strip()

    if not payment_reference:
        raise ValidationError(
            "Payment reference haiwezi kuwa tupu."
        )

    # Lock the listing so two payment requests cannot
    # process the same listing simultaneously.
    listing = (
        Listing.objects
        .select_for_update()
        .select_related("seller", "category")
        .get(pk=listing.pk)
    )

    listing_fee = (
        ListingFee.objects
        .select_for_update()
        .get(listing=listing)
    )

    # Only DRAFT listings can enter the approval process.
    if listing.status != Listing.Status.DRAFT:
        raise ValidationError(
            "Ada inaweza kulipwa tu kwa tangazo lenye hali ya DRAFT."
        )

    # Prevent paying the same fee twice.
    if listing_fee.payment_status == ListingFee.PaymentStatus.PAID:
        raise ValidationError(
            "Ada ya tangazo hili tayari imelipwa."
        )

    # Prevent duplicate payment references.
    if ListingFee.objects.filter(
        payment_reference=payment_reference
    ).exclude(pk=listing_fee.pk).exists():
        raise ValidationError(
            "Payment reference hii tayari imetumika."
        )

    listing_fee.payment_status = ListingFee.PaymentStatus.PAID
    listing_fee.payment_reference = payment_reference
    listing_fee.paid_at = timezone.now()

    listing_fee.save(
        update_fields=[
            "payment_status",
            "payment_reference",
            "paid_at",
            "updated_at",
        ]
    )

    # Payment successful → listing enters admin review.
    listing.status = Listing.Status.PENDING_APPROVAL

    listing.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return listing_fee