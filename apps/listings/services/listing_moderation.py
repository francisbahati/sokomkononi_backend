# apps/listings/services/listing_moderation.py
"""
Listing moderation: 5 actions
  • request_edit_listing       — admin → seller: "hariri kwanza"
  • reject_listing             — admin → seller: "kataa kabisa"
  • request_payment_listing    — admin → seller: "lipa fee" (au idhinisha kama bure)
  • finalize_approval_listing  — admin → seller: "idhinisha mwisho"
  • approve_listing            — legacy: idhinisha moja kwa moja
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _, override
from rest_framework.exceptions import ValidationError

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Listing, ListingFee, ListingFeeRule
from ._lang import user_lang


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
    """
    Tuma notification kwa seller kwa lugha yake.

    `title` na `message` zinapaswa kuwa **tayari zimetafsiriwa**
    (kupitia `_()` + `override(lang)`) kabla ya kuita function hii.
    """
    seller = listing.seller
    listing_id_value = listing.id
    prio = priority or Notification.Priority.NORMAL
    lang = user_lang(seller)

    def _send():
        with override(lang):
            create_notification(
                recipient=seller,
                notification_type=ntype,
                title=title,
                message=message,
                priority=prio,
                related_object_type="Listing",
                related_object_id=listing_id_value,
                action_url="/dashboard/listings",
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

    lang = user_lang(listing.seller)
    with override(lang):
        _notify_seller(
            listing,
            Notification.NotificationType.LISTING_NEEDS_EDIT,
            _("Admin ameomba uhariri wa tangazo"),
            _(
                'Admin ameomba uhariri wa "{title}". Sababu: {reason}'
            ).format(title=listing.title, reason=reason),
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

    lang = user_lang(listing.seller)
    with override(lang):
        _notify_seller(
            listing,
            Notification.NotificationType.LISTING_REJECTED,
            _("Tangazo limekataliwa"),
            _(
                'Tangazo lako "{title}" halikuidhinishwa. Sababu: {reason}'
            ).format(title=listing.title, reason=rejection_reason),
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

    # ✅ Angalia kama fee imezimwa (amount == 0) au haina fee rule
    from django.core.exceptions import ValidationError as DjangoValidationError
    from .listing_fee import create_listing_fee, ListingFeeNotConfigured

    is_free = False
    try:
        fee = create_listing_fee(listing)
        if fee.amount == 0:
            is_free = True
    except ListingFeeNotConfigured:
        # Category haina rule ya ada: usiipeleke LIVE bure kimya kimya.
        raise ValidationError({
            "detail": _(
                "Kundi hili halina kanuni ya ada. Weka ada kwenye mipangilio "
                "kabla ya kuendelea."
            ),
            "code": "FEE_NOT_CONFIGURED",
        })
    except DjangoValidationError:
        # Kama hakuna fee rule kabisa, mfumo unaruhusu LIVE
        is_free = True

    if is_free:
        # ✅ Bypass malipo: Mpeleke LIVE moja kwa moja
        listing.status = Listing.Status.LIVE
        listing.approved_by = admin_user
        listing.approved_at = timezone.now()
        listing.rejection_reason = ""
        listing.save(update_fields=[
            "status", "approved_by", "approved_at",
            "rejection_reason", "updated_at",
        ])

        lang = user_lang(listing.seller)
        with override(lang):
            _notify_seller(
                listing,
                Notification.NotificationType.LISTING_FINAL_APPROVED,
                _("Tangazo lako liko hewani!"),
                _(
                    'Tangazo lako "{title}" limeidhinishwa bila malipo '
                    "na sasa linaonekana kwa wanunuzi."
                ).format(title=listing.title),
                priority=Notification.Priority.HIGH,
            )
        return listing

    # Kama fee ipo (si sifuri), endelea na mtiririko wa kawaida wa malipo
    listing.status = Listing.Status.APPROVED_PENDING_PAYMENT
    listing.approved_by = admin_user
    listing.approved_at = timezone.now()
    listing.save(update_fields=[
        "status", "approved_by", "approved_at", "updated_at",
    ])

    clean_reason = (reason or "").strip()
    lang = user_lang(listing.seller)
    with override(lang):
        msg = _(
            'Tangazo lako "{title}" limekaguliwa na ni zuri. '
            "Tafadhali lipa ada ya kuchapisha ili liidhinishwe."
        ).format(title=listing.title)
        if clean_reason:
            msg += " " + _("Maelezo: {notes}").format(notes=clean_reason)

        _notify_seller(
            listing,
            Notification.NotificationType.LISTING_PAYMENT_REQUESTED,
            _("Lipa ada ya kuchapisha tangazo"),
            msg,
            priority=Notification.Priority.HIGH,
        )

    return listing


# ============================================================
# 4. FINALIZE APPROVAL — admin analidhinisha mwisho
# ============================================================
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

    lang = user_lang(listing.seller)
    with override(lang):
        _notify_seller(
            listing,
            Notification.NotificationType.LISTING_FINAL_APPROVED,
            _("Tangazo lako liko hewani!"),
            _(
                'Tangazo lako "{title}" limeidhinishwa na sasa '
                "linaonekana kwa wanunuzi."
            ).format(title=listing.title),
            priority=Notification.Priority.HIGH,
        )

    return listing


# ============================================================
# 5. APPROVE (legacy) — idhinisha moja kwa moja
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

    lang = user_lang(listing.seller)
    with override(lang):
        _notify_seller(
            listing,
            Notification.NotificationType.LISTING_APPROVED,
            _("Tangazo limeidhinishwa"),
            _(
                'Tangazo lako "{title}" limeidhinishwa na sasa '
                "linapatikana."
            ).format(title=listing.title),
            priority=Notification.Priority.HIGH,
        )

    return listing


# ============================================================
# NOTIFY ADMINS — tangazo jipya limewasilishwa (publish / edit ya LIVE)
# ============================================================
def notify_admins_listing_submitted(listing):
    """Tuma notification kwa admins wote tangazo linapoingia kwenye foleni."""
    from apps.notifications.services.notification import (
        create_notification_for_admins,
    )

    seller = listing.seller
    seller_label = (
        getattr(seller, "name", "") or getattr(seller, "phone", "") or "—"
    )
    title_text = listing.title
    listing_id_value = listing.id

    def _send():
        try:
            create_notification_for_admins(
                notification_type=Notification.NotificationType.LISTING_CREATED,
                title=_("Tangazo jipya linasubiri ukaguzi"),
                message=_('"{title}" imewasilishwa na {seller}.').format(
                    title=title_text, seller=seller_label
                ),
                related_object_type="listings.Listing",
                related_object_id=listing_id_value,
                action_url="/smk-control-9x7k/moderation",
                priority=Notification.Priority.HIGH,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "admin notification for submitted listing failed"
            )

    transaction.on_commit(_send)