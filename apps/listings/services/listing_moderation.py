from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import Listing, ListingFee


@transaction.atomic
def approve_listing(listing_id, admin_user):
    """
    Approve a listing after verifying that:
    - The user is an admin/staff member.
    - The listing is pending approval.
    - The listing fee exists and has been paid.
    """

    if not admin_user or not admin_user.is_authenticated:
        raise ValidationError(
            "Ni lazima uwe umeingia kwenye akaunti."
        )

    if not admin_user.is_staff:
        raise ValidationError(
            "Ni wasimamizi wa mfumo pekee wanaoweza kuidhinisha matangazo."
        )

    listing = (
        Listing.objects
        .select_for_update()
        .select_related("seller", "category")
        .get(pk=listing_id)
    )

    if listing.status != Listing.Status.PENDING_APPROVAL:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kusubiri idhini."
        )

    try:
        listing_fee = (
            ListingFee.objects
            .select_for_update()
            .get(listing=listing)
        )
    except ListingFee.DoesNotExist:
        raise ValidationError(
            "Tangazo hili halina ada ya tangazo."
        )

    if listing_fee.payment_status != ListingFee.PaymentStatus.PAID:
        raise ValidationError(
            "Tangazo hili haliwezi kuidhinishwa kwa sababu ada ya "
            "tangazo haijalipwa."
        )

    listing.status = Listing.Status.AVAILABLE
    listing.approved_by = admin_user
    listing.approved_at = timezone.now()

    # Clear previous rejection information in case
    # an administrator is re-approving a previously rejected listing.
    listing.rejected_by = None
    listing.rejected_at = None
    listing.rejection_reason = ""

    listing.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )

    return listing


@transaction.atomic
def reject_listing(listing_id, admin_user, rejection_reason):
    """
    Reject a listing that is waiting for admin approval.
    """

    if not admin_user or not admin_user.is_authenticated:
        raise ValidationError(
            "Ni lazima uwe umeingia kwenye akaunti."
        )

    if not admin_user.is_staff:
        raise ValidationError(
            "Ni wasimamizi wa mfumo pekee wanaoweza kukataa matangazo."
        )

    rejection_reason = (rejection_reason or "").strip()

    if not rejection_reason:
        raise ValidationError(
            "Sababu ya kukataa tangazo inahitajika."
        )

    listing = (
        Listing.objects
        .select_for_update()
        .select_related("seller", "category")
        .get(pk=listing_id)
    )

    if listing.status != Listing.Status.PENDING_APPROVAL:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kusubiri idhini."
        )

    listing.status = Listing.Status.REJECTED
    listing.rejected_by = admin_user
    listing.rejected_at = timezone.now()
    listing.rejection_reason = rejection_reason

    # Clear approval information.
    listing.approved_by = None
    listing.approved_at = None

    listing.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )

    return listing