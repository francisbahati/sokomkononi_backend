from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Listing, ListingFee, ListingFeeRule


# ═════════════════════════════════════════════════════════════════
# HELPER: Angalia kama fee inahitajika kwa listing hii
# ═════════════════════════════════════════════════════════════════
def _is_listing_fee_required_for(listing):
    """
    Rudisha True kama fee inahitajika kwa category ya listing hii.

    Kanuni:
      1. Kama category ina ListingFeeRule active → fee inahitajika
      2. Kama hakuna rule yoyote active → fee HAIHITAJIKI (bure)
      3. Kama rule.flat_fee == 0 na rule.percentage == 0 → fee HAIHITAJIKI
    """
    if not listing.category_id:
        # Listing haina category — kwa kawaida fee inahitajika
        return True

    category = listing.category
    category_slug = getattr(category, "slug", None)

    # Tafuta rule active ya category hii
    rule = None

    if category is not None:
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
        # No explicit rule exists. Auto-create a rule with the default
        # flat fee (see apps/listings/services/listing_fee.py) so the
        # seller sees a real amount instead of "TZS 0".
        #
        # This matches the behaviour of get_listing_fee_rule() so the two
        # code paths never disagree about whether a fee applies.
        try:
            from .listing_fee import get_listing_fee_rule

            rule = get_listing_fee_rule(
                category_slug=category_slug,
                category=category,
            )
        except Exception:
            rule = None

        if not rule:
            return False

    # Rule ipo — angalia kama bei ni 0
    flat = float(rule.flat_fee or 0)
    pct = float(rule.percentage or 0)

    if rule.fee_mode == "FLAT" and flat == 0:
        return False

    if rule.fee_mode == "PERCENTAGE" and pct == 0:
        return False

    return True


# ═════════════════════════════════════════════════════════════════
# APPROVE LISTING
# ═════════════════════════════════════════════════════════════════
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

    # ─────────────────────────────────────────────────────────
    # Angalia kama fee inahitajika kwa category hii
    # ─────────────────────────────────────────────────────────
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
                "Tangazo hili halina ada ya tangazo. "
                "Tafadhali hakikisha muuzaji amelipa ada kwanza."
            )

        if listing_fee.payment_status != ListingFee.PaymentStatus.PAID:
            raise ValidationError(
                "Tangazo hili haliwezi kuidhinishwa kwa sababu ada ya "
                "tangazo haijalipwa."
            )

    # ─────────────────────────────────────────────────────────
    # Endelea na approve
    # ─────────────────────────────────────────────────────────
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


# ═════════════════════════════════════════════════════════════════
# REJECT LISTING
# ═════════════════════════════════════════════════════════════════
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