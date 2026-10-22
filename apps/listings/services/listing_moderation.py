# apps/listings/services/listing_moderation.py
"""
Listing moderation: 5 actions
  • request_edit_listing       — admin → seller: "hariri kwanza"
  • reject_listing             — admin → seller: "kataa kabisa"
  • request_payment_listing    — admin → seller: "lipa fee"
  • finalize_approval_listing  — admin → seller: "idhinisha mwisho"
  • approve_listing            — legacy: idhinisha moja kwa moja
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Listing, ListingFee, ListingFeeRule


def _require_admin(admin_user):
    if not admin_user or not admin_user.is_authenticated:
        raise ValidationError("Ni lazima uwe umeingia kwenye akaunti.")
    if not admin_user.is_staff:
        raise ValidationError(
            "Ni wasimamizi wa mfumo pekee wanaoweza kufanya hivi."
        )


def _get_locked_listing(listing_id):
    return (
        Listing.objects
        .select_for_update(of=("self",))
        .select_related("seller", "category")
        .get(pk=listing_id)
    )


def _notify_seller(listing, ntype, title, message, priority=None):
    seller = listing.seller
    listing_title = listing.title
    listing_id_value = listing.id
    prio = priority or Notification.Priority.NORMAL

    def _send():
        create_notification(
            recipient=seller,
            notification_type=ntype,
            title=title,
            message=message,
            priority=prio,
            related_object_type="Listing",
            related_object_id=listing_id_value,
            action_url=f"/dashboard/listings",
        )

    transaction.on_commit(_send)


# ============================================================
# 1. REQUEST EDIT — admin anarudisha kwa seller kwa mabadiliko
# ============================================================
@transaction.atomic
def request_edit_listing(listing_id, admin_user, reason):
    _require_admin(admin_user)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError("Sababu inahitajika (herufi 5+).")

    listing = _get_locked_listing(listing_id)

    if listing.status not in (
        Listing.Status.PENDING_APPROVAL,
        Listing.Status.PAID_PENDING_APPROVAL,
    ):
        raise ValidationError(
            "Tangazo hili halipo kwenye hali inayoruhusu kuomba uhariri."
        )

    listing.status = Listing.Status.NEEDS_EDIT
    listing.rejection_reason = reason
    listing.rejected_by = admin_user
    listing.rejected_at = timezone.now()
    listing.save(update_fields=[
        "status", "rejection_reason",
        "rejected_by", "rejected_at", "updated_at",
    ])

    _notify_seller(
        listing,
        Notification.NotificationType.LISTING_NEEDS_EDIT,
        "Admin ameomba uhariri wa tangazo",
        f'Admin ameomba uhariri wa "{listing.title}". Sababu: {reason}',
        priority=Notification.Priority.HIGH,
    )

    return listing


# ============================================================
# 2. REJECT — kataa kabisa
# ============================================================
@transaction.atomic
def reject_listing(listing_id, admin_user, rejection_reason):
    _require_admin(admin_user)
    rejection_reason = (rejection_reason or "").strip()
    if not rejection_reason:
        raise ValidationError("Sababu ya kukataa tangazo inahitajika.")

    listing = _get_locked_listing(listing_id)

    if listing.status not in (
        Listing.Status.PENDING_APPROVAL,
        Listing.Status.PAID_PENDING_APPROVAL,
        Listing.Status.APPROVED_PENDING_PAYMENT,
        Listing.Status.NEEDS_EDIT,
    ):
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kukataliwa."
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

    _notify_seller(
        listing,
        Notification.NotificationType.LISTING_REJECTED,
        "Tangazo limekataliwa",
        f'Tangazo lako "{listing.title}" halikuidhinishwa. Sababu: {rejection_reason}',
        priority=Notification.Priority.URGENT,
    )

    return listing


# ============================================================
# 3. REQUEST PAYMENT — admin ameona ni nzuri, mwambie seller alipe
# ============================================================
@transaction.atomic
def request_payment_listing(listing_id, admin_user, reason=""):
    _require_admin(admin_user)

    listing = _get_locked_listing(listing_id)

    if listing.status != Listing.Status.PENDING_APPROVAL:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kusubiri idhini."
        )

    # Hakikisha ada ipo kabla ya kumwomba seller alipe. Hapa ndipo admin
    # anaarifiwa kama kundi (category) halina fee rule.
    from django.core.exceptions import ValidationError as DjangoValidationError
    from .listing_fee import create_listing_fee
    try:
        create_listing_fee(listing)
    except DjangoValidationError:
        raise ValidationError(
            "Ada ya kundi hili haijasanidiwa. Weka fee rule kwa kundi hili "
            "(Revenue -> Listing Fee) kisha ujaribu tena."
        )

    listing.status = Listing.Status.APPROVED_PENDING_PAYMENT
    listing.approved_by = admin_user
    listing.approved_at = timezone.now()
    listing.save(update_fields=[
        "status", "approved_by", "approved_at", "updated_at",
    ])

    clean_reason = (reason or "").strip()
    msg = (
        f'Tangazo lako "{listing.title}" limekaguliwa na ni zuri. '
        f"Tafadhali lipa ada ya kuchapisha ili liidhinishwe."
    )
    if clean_reason:
        msg = f"{msg} Maelezo: {clean_reason}"

    _notify_seller(
        listing,
        Notification.NotificationType.LISTING_PAYMENT_REQUESTED,
        "Lipa ada ya kuchapisha tangazo",
        msg,
        priority=Notification.Priority.HIGH,
    )

    return listing


# ============================================================
# 4. FINALIZE APPROVAL — admin analidhinisha mwisho
# # ============================================================
@transaction.atomic
def finalize_approval_listing(listing_id, admin_user):
    _require_admin(admin_user)

    listing = _get_locked_listing(listing_id)

    if listing.status != Listing.Status.PAID_PENDING_APPROVAL:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kusubiri idhini ya mwisho."
        )

    fee = getattr(listing, "listing_fee", None)
    if fee is not None and fee.payment_status != ListingFee.PaymentStatus.PAID:
        raise ValidationError(
            "Ada ya tangazo hili haijalipwa bado."
        )

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

    _notify_seller(
        listing,
        Notification.NotificationType.LISTING_FINAL_APPROVED,
        "Tangazo lako liko hewani!",
        f'Tangazo lako "{listing.title}" limeidhinishwa na sasa linaonekana kwa wanunuzi.',
        priority=Notification.Priority.HIGH,
    )

    return listing

# ============================================================

# ============================================================
@transaction.atomic
def approve_listing(listing_id, admin_user):
    _require_admin(admin_user)

    listing = _get_locked_listing(listing_id)

    if listing.status != Listing.Status.PENDING_APPROVAL:
        raise ValidationError(
            "Tangazo hili halipo kwenye hali ya kusubiri idhini."
        )

    # ── Zuia approve isiruke malipo ──────────────────────────
    listing_fee = getattr(listing, "listing_fee", None)
    fee_is_paid = (
        listing_fee is not None
        and listing_fee.payment_status == ListingFee.PaymentStatus.PAID
    )
    fee_is_free = listing_fee is None or listing_fee.amount == 0

    if not fee_is_paid and not fee_is_free:
        raise ValidationError(
            "Tangazo hili linahitaji malipo. Tumia 'Omba Malipo' "
            "kwanza, kisha 'Idhinisha Mwisho' baada ya seller kulipa."
        )
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

    _notify_seller(
        listing,
        Notification.NotificationType.LISTING_APPROVED,
        "Tangazo limeidhinishwa",
        f'Tangazo lako "{listing.title}" limeidhinishwa na sasa linapatikana.',
        priority=Notification.Priority.HIGH,
    )

    return listing