
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing
from apps.notifications.services.notification import create_notification

from ..models import BoostPackage, ListingBoost


# ============================================================================
# BOOST FEE
# ============================================================================

def calculate_boost_fee(*, package):
    """
    Return the configured price for a boost package.

    The package price is stored by the admin and is returned as a Decimal
    rounded to two decimal places.
    """

    if not isinstance(package, BoostPackage):
        raise ValidationError("Boost package si sahihi.")

    if not package.is_active:
        raise ValidationError("Boost package hii haipo active.")

    amount = Decimal(package.price).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Bei ya boost lazima iwe kubwa kuliko sifuri."
        )

    return amount


# ============================================================================
# VALIDATION
# ============================================================================

def validate_boost_request(*, listing, user, package):
    """
    Validate all business rules before creating a boost.
    """

    if not user or not user.is_authenticated:
        raise ValidationError(
            "Lazima uwe umeingia kwenye akaunti."
        )

    if not user.is_active:
        raise ValidationError(
            "Akaunti yako haipo active."
        )

    if not user.is_verified:
        raise ValidationError(
            "Akaunti yako lazima iwe imethibitishwa."
        )

    if listing.seller_id != user.id:
        raise ValidationError(
            "Huruhusiwi ku-boost tangazo ambalo si lako."
        )

    if listing.status != Listing.Status.AVAILABLE:
        raise ValidationError(
            "Tangazo lazima liwe AVAILABLE kabla ya ku-boost."
        )

    if not package.is_active:
        raise ValidationError(
            "Boost package hii haipo active."
        )

    # Do not allow a new boost while another one is still active.
    now = timezone.now()

    active_boost_exists = ListingBoost.objects.filter(
        listing=listing,
        status=ListingBoost.BoostStatus.ACTIVE,
        expires_at__gt=now,
    ).exists()

    if active_boost_exists:
        raise ValidationError(
            "Tangazo hili tayari lina boost active."
        )


# ============================================================================
# CREATE BOOST
# ============================================================================

@db_transaction.atomic
def create_boost(*, listing, user, package):
    """
    Create a pending boost payment.

    This does NOT activate the boost yet.

    The flow is:

        Seller
            ↓
        Create Boost
            ↓
        PENDING
            ↓
        Payment
            ↓
        Mark as PAID
            ↓
        Activate Boost
    """

    # Lock the listing to prevent two simultaneous boost requests.
    listing = (
        Listing.objects
        .select_for_update()
        .select_related("seller")
        .get(pk=listing.pk)
    )

    # Lock the package as well.
    package = (
        BoostPackage.objects
        .select_for_update()
        .get(pk=package.pk)
    )

    validate_boost_request(
        listing=listing,
        user=user,
        package=package,
    )

    amount = calculate_boost_fee(package=package)

    boost = ListingBoost.objects.create(
        listing=listing,
        seller=user,
        package=package,
        amount=amount,
        payment_status=ListingBoost.PaymentStatus.PENDING,
        status=ListingBoost.BoostStatus.PENDING,
    )

    return boost


# ============================================================================
# MARK BOOST PAYMENT AS PAID
# ============================================================================

@db_transaction.atomic
def mark_boost_as_paid(*, boost, payment_reference):
    """
    Mark a boost payment as paid.

    This function records the payment but does not activate the boost.
    Activation is handled separately by activate_boost().
    """

    if not payment_reference:
        raise ValidationError(
            "Payment reference inahitajika."
        )

    payment_reference = str(payment_reference).strip()

    if not payment_reference:
        raise ValidationError(
            "Payment reference haiwezi kuwa tupu."
        )

    boost = (
        ListingBoost.objects
        .select_for_update()
        .select_related("listing", "seller", "package")
        .get(pk=boost.pk)
    )

    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        raise ValidationError(
            "Boost hii tayari imelipiwa."
        )

    if boost.status in [
        ListingBoost.BoostStatus.CANCELLED,
        ListingBoost.BoostStatus.EXPIRED,
    ]:
        raise ValidationError(
            "Boost hii haiwezi kulipiwa kwa sababu imefungwa."
        )

    # Payment references must be unique.
    reference_exists = (
        ListingBoost.objects
        .filter(payment_reference=payment_reference)
        .exclude(pk=boost.pk)
        .exists()
    )

    if reference_exists:
        raise ValidationError(
            "Payment reference hii tayari imetumika."
        )

    boost.payment_status = ListingBoost.PaymentStatus.PAID
    boost.payment_reference = payment_reference
    boost.paid_at = timezone.now()

    boost.save(
        update_fields=[
            "payment_status",
            "payment_reference",
            "paid_at",
            "updated_at",
        ]
    )

    return boost


# ============================================================================
# ACTIVATE BOOST
# ============================================================================

@db_transaction.atomic
def activate_boost(*, boost):
    """
    Activate a successfully paid boost.

    This updates:

        Listing.is_boosted = True
        Listing.boosted_until = calculated expiry

    and creates the BOOST_ACTIVATED notification.
    """

    boost = (
        ListingBoost.objects
        .select_for_update()
        .select_related(
            "listing",
            "seller",
            "package",
        )
        .get(pk=boost.pk)
    )

    if boost.payment_status != ListingBoost.PaymentStatus.PAID:
        raise ValidationError(
            "Boost lazima iwe imelipiwa kabla ya ku-activate."
        )

    if boost.status == ListingBoost.BoostStatus.ACTIVE:
        raise ValidationError(
            "Boost hii tayari ipo active."
        )

    if boost.status in [
        ListingBoost.BoostStatus.CANCELLED,
        ListingBoost.BoostStatus.EXPIRED,
    ]:
        raise ValidationError(
            "Boost hii haiwezi ku-activate."
        )

    listing = (
        Listing.objects
        .select_for_update()
        .get(pk=boost.listing_id)
    )

    if listing.seller_id != boost.seller_id:
        raise ValidationError(
            "Seller wa boost haendani na seller wa listing."
        )

    if listing.status != Listing.Status.AVAILABLE:
        raise ValidationError(
            "Tangazo lazima liwe AVAILABLE wakati boost ina-activate."
        )

    now = timezone.now()

    # Prevent overlapping active boosts.
    active_boost_exists = (
        ListingBoost.objects
        .filter(
            listing_id=listing.id,
            status=ListingBoost.BoostStatus.ACTIVE,
            expires_at__gt=now,
        )
        .exclude(pk=boost.pk)
        .exists()
    )

    if active_boost_exists:
        raise ValidationError(
            "Tangazo hili tayari lina boost nyingine active."
        )

    starts_at = now
    expires_at = starts_at + timedelta(
        hours=boost.package.duration_hours
    )

    boost.status = ListingBoost.BoostStatus.ACTIVE
    boost.starts_at = starts_at
    boost.expires_at = expires_at

    boost.save(
        update_fields=[
            "status",
            "starts_at",
            "expires_at",
            "updated_at",
        ]
    )

    listing.is_boosted = True
    listing.boosted_until = expires_at

    listing.save(
        update_fields=[
            "is_boosted",
            "boosted_until",
            "updated_at",
        ]
    )

    create_notification(
        recipient=boost.seller,
        notification_type="BOOST_ACTIVATED",
        title="Boost imewashwa",
        message=(
            f'Boost ya tangazo "{listing.title}" imewashwa '
            f'hadi {expires_at.strftime("%Y-%m-%d %H:%M")}.'
        ),
        related_object_type="listing",
        related_object_id=listing.id,
        action_url=f"/listings/{listing.id}/",
        priority="NORMAL",
    )

    return boost


# ============================================================================
# PAY + ACTIVATE
# ============================================================================

@db_transaction.atomic
def pay_and_activate_boost(*, boost, payment_reference):
    """
    Development-friendly helper.

    Simulates the complete flow:

        PENDING
            ↓
        PAID
            ↓
        ACTIVE

    Later the real payment gateway/webhook can call the individual
    payment and activation services instead.
    """

    boost = mark_boost_as_paid(
        boost=boost,
        payment_reference=payment_reference,
    )

    boost = activate_boost(
        boost=boost,
    )

    return boost


# ============================================================================
# EXPIRE BOOST
# ============================================================================

@db_transaction.atomic
def expire_boost(*, boost):
    """
    Expire an active boost after its expiry time.
    """

    boost = (
        ListingBoost.objects
        .select_for_update()
        .select_related("listing")
        .get(pk=boost.pk)
    )

    if boost.status != ListingBoost.BoostStatus.ACTIVE:
        raise ValidationError(
            "Boost hii haipo active."
        )

    now = timezone.now()

    if not boost.expires_at:
        raise ValidationError(
            "Boost haina expiry time."
        )

    if boost.expires_at > now:
        raise ValidationError(
            "Boost bado haija-expire."
        )

    boost.status = ListingBoost.BoostStatus.EXPIRED

    boost.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    listing = (
        Listing.objects
        .select_for_update()
        .get(pk=boost.listing_id)
    )

    # Only remove the listing-level boost if this boost is the one
    # currently controlling the listing.
    if (
        listing.boosted_until
        and listing.boosted_until <= now
    ):
        listing.is_boosted = False
        listing.boosted_until = None

        listing.save(
            update_fields=[
                "is_boosted",
                "boosted_until",
                "updated_at",
            ]
        )

    return boost


# ============================================================================
# CANCEL BOOST
# ============================================================================

@db_transaction.atomic
def cancel_boost(*, boost, user):
    """
    Cancel a pending boost.

    Active boosts should normally be handled through an admin/refund
    workflow rather than simply cancelled.
    """

    boost = (
        ListingBoost.objects
        .select_for_update()
        .select_related("listing", "seller")
        .get(pk=boost.pk)
    )

    if not user or not user.is_authenticated:
        raise ValidationError(
            "Lazima uwe umeingia kwenye akaunti."
        )

    if not user.is_staff and boost.seller_id != user.id:
        raise ValidationError(
            "Huruhusiwi kufuta boost hii."
        )

    if boost.status == ListingBoost.BoostStatus.ACTIVE:
        raise ValidationError(
            "Boost active haiwezi kufutwa kupitia endpoint hii."
        )

    if boost.status == ListingBoost.BoostStatus.EXPIRED:
        raise ValidationError(
            "Boost hii tayari ime-expire."
        )

    if boost.status == ListingBoost.BoostStatus.CANCELLED:
        raise ValidationError(
            "Boost hii tayari ime-cancel."
        )

    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        raise ValidationError(
            "Boost iliyolipiwa haiwezi ku-cancel bila refund workflow."
        )

    boost.status = ListingBoost.BoostStatus.CANCELLED

    boost.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return boost