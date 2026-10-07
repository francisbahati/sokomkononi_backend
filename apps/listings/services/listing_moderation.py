# apps/listings/services/listing_moderation.py
"""
Listing moderation: approve / reject + fee-required detection.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Listing, ListingFee, ListingFeeRule


# ============================================================
# FEE-REQUIRED DETECTION
# ============================================================

def _is_listing_fee_required_for(listing):
    """
    Determine whether this listing requires a paid fee before approval.

    Returns True when:
      - The category has NO rule (fee must be configured before approval)
      - The category has a rule with a non-zero flat_fee or percentage

    Returns False when:
      - The category has a rule with flat_fee=0 (or percentage=0) —
        the admin has explicitly configured this category as free.

    This function does NOT auto-create rules. Missing rules are a
    configuration issue that must be fixed by the admin.
    """
    if not listing.category_id:
        # No category → cannot confirm free → treat as fee-required
        return True

    category = listing.category
    category_slug = getattr(category, "slug", None)

    rule = (
        ListingFeeRule.objects
        .filter(category=category, is_active=True, is_deleted=False)
        .order_by("priority")
        .first()
    )
    if not rule and category_slug:
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

    if not rule:
        # No rule → require configuration. The caller (perform_create
        # or approve_listing) will raise ListingFeeNotConfigured.
        return True

    flat = Decimal(str(rule.flat_fee or 0))
    pct = Decimal(str(rule.percentage or 0))

    if rule.fee_mode == "FLAT":
        return flat > Decimal("0")
    return pct > Decimal("0")


# ============================================================
# APPROVE
# ============================================================

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
        .select_for_update(of=("self",))
        .select_related("seller", "category")
        .get(pk=listing_id)
    )

    if listing.status != Listing.Status.PENDING_APPROVAL:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kusubiri idhini."
        )

    # Verify the fee has been paid when one was required.
    fee_required = _is_listing_fee_required_for(listing)

    if fee_required:
        try:
            listing_fee = (
                ListingFee.objects
                .select_for_update()
                .get(listing=listing)
            )
        except ListingFee.DoesNotExist:
            raise ValidationError(
                "Tangazo hili halina rekodi ya ada. "
                "Tafadhali hakikisha muuzaji amelipa ada kwanza."
            )

        if listing_fee.payment_status != ListingFee.PaymentStatus.PAID:
            raise ValidationError(
                "Tangazo hili haliwezi kuidhinishwa kwa sababu ada ya "
                "tangazo haijalipwa."
            )

    # Approve
    listing.status = Listing.Status.LIVE
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


# ============================================================
# REJECT
# ============================================================

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
        .select_for_update(of=("self",))
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
