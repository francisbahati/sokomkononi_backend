from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Listing, ListingFee


@transaction.atomic
def approve_listing(listing_id, admin_user):
    if not admin_user or not admin_user.is_authenticated:
        raise ValidationError("Ni lazima uwe umeingia kwenye akaunti.")
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
        raise ValidationError("Tangazo hili halina ada ya tangazo.")

    if listing_fee.payment_status != ListingFee.PaymentStatus.PAID:
        raise ValidationError(
            "Tangazo hili haliwezi kuidhinishwa kwa sababu ada ya "
            "tangazo haijalipwa."
        )

    listing.status = Listing.Status.AVAILABLE
    listing.approved_by = admin_user
    listing.approved_at = timezone.now()
    listing.rejected_by = None
    listing.rejected_at = None
    listing.rejection_reason = ""

    listing.save(update_fields=[
        "status", "approved_by", "approved_at",
        "rejected_by", "rejected_at", "rejection_reason", "updated_at",
    ])

    seller = listing.seller
    listing_title = listing.title
    listing_id_value = listing.id

    transaction.on_commit(
        lambda: create_notification(
            recipient=seller,
            notification_type=(
                Notification.NotificationType.LISTING_APPROVED
            ),
            title="Tangazo limeidhinishwa",
            message=(
                f"Tangazo lako '{listing_title}' limeidhinishwa "
                f"na sasa linapatikana kwa wanunuzi."
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="Listing",
            related_object_id=listing_id_value,
            action_url=f"/listings/{listing_id_value}/",
        )
    )

    return listing


@transaction.atomic
def reject_listing(listing_id, admin_user, rejection_reason):
    if not admin_user or not admin_user.is_authenticated:
        raise ValidationError("Ni lazima uwe umeingia kwenye akaunti.")
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
    listing.approved_by = None
    listing.approved_at = None

    listing.save(update_fields=[
        "status", "rejected_by", "rejected_at", "rejection_reason",
        "approved_by", "approved_at", "updated_at",
    ])

    seller = listing.seller
    listing_title = listing.title
    listing_id_value = listing.id
    reason = rejection_reason

    transaction.on_commit(
        lambda: create_notification(
            recipient=seller,
            notification_type=(
                Notification.NotificationType.LISTING_REJECTED
            ),
            title="Tangazo limekataliwa",
            message=(
                f"Tangazo lako '{listing_title}' halikuidhinishwa. "
                f"Sababu: {reason}"
            ),
            priority=Notification.Priority.URGENT,
            related_object_type="Listing",
            related_object_id=listing_id_value,
            action_url=f"/listings/{listing_id_value}/",
        )
    )

    return listing