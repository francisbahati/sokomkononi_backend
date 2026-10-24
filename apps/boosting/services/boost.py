import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing


from decimal import Decimal
try:
    from apps.notifications.services.notification import create_notification
except (ImportError, LookupError):
    def create_notification(**kwargs):
        return None

from ..models import BoostFeeConfig, BoostPackage, ListingBoost

logger = logging.getLogger(__name__)


def is_boost_fee_enabled():
    """True when boosts must be paid; False when boosting is free."""
    return BoostFeeConfig.get_solo().is_active


def calculate_boost_fee(*, package):
    if not isinstance(package, BoostPackage):
        raise ValidationError("Boost package si sahihi.")

    if not package.is_active:
        raise ValidationError("Boost package hii haipo active.")

    # Fee disabled by admin -> boosting is free.
    if not is_boost_fee_enabled():
        return Decimal("0.00")

    amount = Decimal(package.price).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Bei ya boost lazima iwe kubwa kuliko sifuri."
        )

    return amount


def validate_boost_request(*, listing, user, package):
    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not user.is_active:
        raise ValidationError("Akaunti yako haipo active.")
    if not user.is_verified:
        raise ValidationError("Akaunti yako lazima iwe imethibitishwa.")

    if listing.seller_id != user.id:
        raise ValidationError("Huruhusiwi ku-boost tangazo ambalo si lako.")

    if listing.status != Listing.Status.LIVE:
        raise ValidationError(
            "Tangazo lazima liwe AVAILABLE kabla ya ku-boost."
        )

    if not package.is_active:
        raise ValidationError("Boost package hii haipo active.")

    now = timezone.now()
    if ListingBoost.objects.filter(listing=listing).filter(
        models.Q(status=ListingBoost.BoostStatus.ACTIVE, expires_at__gt=now)
        | models.Q(payment_status=ListingBoost.PaymentStatus.PENDING)
    ).exists():
        raise ValidationError(
            "Tangazo hili tayari lina boost active au inayosubiri malipo."
        )


@db_transaction.atomic
def create_boost(*, listing, user, package):
    listing = (
        Listing.objects
        .select_for_update(of=("self",))
        .select_related("seller")
        .get(pk=listing.pk)
    )
    package = BoostPackage.objects.select_for_update().get(pk=package.pk)

    validate_boost_request(listing=listing, user=user, package=package)

    amount = calculate_boost_fee(package=package)

    return ListingBoost.objects.create(
        listing=listing,
        seller=user,
        package=package,
        amount=amount,
        payment_status=ListingBoost.PaymentStatus.PENDING,
        status=ListingBoost.BoostStatus.PENDING,
    )


@db_transaction.atomic
def mark_boost_as_paid(*, boost, payment_reference):
    if not payment_reference:
        raise ValidationError("Payment reference inahitajika.")

    payment_reference = str(payment_reference).strip()

    if not payment_reference:
        raise ValidationError(
            "Payment reference haiwezi kuwa tupu."
        )

    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=boost.pk)
    )

    # Idempotent retry: same reference -> return existing.
    if (
        boost.payment_status == ListingBoost.PaymentStatus.PAID
        and boost.payment_reference == payment_reference
    ):
        return boost

    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        raise ValidationError("Boost hii tayari imelipiwa.")

    if boost.status in [
        ListingBoost.BoostStatus.CANCELLED,
        ListingBoost.BoostStatus.EXPIRED,
    ]:
        raise ValidationError(
            "Boost hii haiwezi kulipiwa kwa sababu imefungwa."
        )

    if ListingBoost.objects.filter(
        payment_reference=payment_reference,
    ).exclude(pk=boost.pk).exists():
        raise ValidationError(
            "Payment reference hii tayari imetumika."
        )

    boost.payment_status = ListingBoost.PaymentStatus.PAID
    boost.payment_reference = payment_reference
    boost.paid_at = timezone.now()

    boost.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])

    return boost


@db_transaction.atomic
def pay_boost_free(*, boost, user):
    """
    Settle a boost without payment. Only valid while the boost fee is
    disabled. Marks the boost PAID with amount 0 so it can be activated
    through the normal activate_boost() flow.
    """
    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=boost.pk)
    )

    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if boost.seller_id != user.id:
        raise ValidationError("Huruhusiwi kuwasha boost hii.")

    if is_boost_fee_enabled():
        raise ValidationError("Ada ya boost imewashwa. Boost lazima ilipiwe.")

    # Idempotent retry.
    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        return boost

    if boost.status in [
        ListingBoost.BoostStatus.CANCELLED,
        ListingBoost.BoostStatus.EXPIRED,
    ]:
        raise ValidationError("Boost hii haiwezi kuwashwa kwa sababu imefungwa.")

    if not boost.package.is_active:
        raise ValidationError("Boost package hii haipo active.")

    boost.amount = Decimal("0.00")
    boost.payment_status = ListingBoost.PaymentStatus.PAID
    boost.payment_reference = f"free-{boost.pk}"
    boost.paid_at = timezone.now()
    boost.save(update_fields=[
        "amount", "payment_status", "payment_reference",
        "paid_at", "updated_at",
    ])

    return boost


@db_transaction.atomic
def activate_boost(*, boost):
    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=boost.pk)
    )

    if boost.payment_status != ListingBoost.PaymentStatus.PAID:
        raise ValidationError(
            "Boost lazima iwe imelipiwa kabla ya ku-activate."
        )

    if boost.status == ListingBoost.BoostStatus.ACTIVE:
        raise ValidationError("Boost hii tayari ipo active.")

    if boost.status in [
        ListingBoost.BoostStatus.CANCELLED,
        ListingBoost.BoostStatus.EXPIRED,
    ]:
        raise ValidationError("Boost hii haiwezi ku-activate.")

    listing = Listing.objects.select_for_update().get(
        pk=boost.listing_id,
    )

    if listing.seller_id != boost.seller_id:
        raise ValidationError(
            "Seller wa boost haendani na seller wa listing."
        )

    if listing.status != Listing.Status.LIVE:
        raise ValidationError(
            "Tangazo lazima liwe AVAILABLE wakati boost ina-activate."
        )

    now = timezone.now()

    if ListingBoost.objects.filter(
        listing_id=listing.id,
        status=ListingBoost.BoostStatus.ACTIVE,
        expires_at__gt=now,
    ).exclude(pk=boost.pk).exists():
        raise ValidationError(
            "Tangazo hili tayari lina boost nyingine active."
        )

    starts_at = now
    expires_at = starts_at + timedelta(hours=boost.package.duration_hours)

    if expires_at <= now:
        raise ValidationError(
            "Muda wa boost uliopangwa tayari umepita."
        )

    boost.status = ListingBoost.BoostStatus.ACTIVE
    boost.starts_at = starts_at
    boost.expires_at = expires_at

    boost.save(update_fields=[
        "status", "starts_at", "expires_at", "updated_at",
    ])

    listing.is_boosted = True
    listing.boosted_until = expires_at
    listing.save(update_fields=["is_boosted", "boosted_until", "updated_at"])

    seller = boost.seller
    listing_title = listing.title
    boost_expires = expires_at

    db_transaction.on_commit(
        lambda: create_notification(
            recipient=seller,
            notification_type="BOOST_ACTIVATED",
            title="Boost imewashwa",
            message=(
                f'Boost ya tangazo "{listing_title}" imewashwa '
                f'hadi {boost_expires.strftime("%Y-%m-%d %H:%M")}.'
            ),
            related_object_type="listing",
            related_object_id=listing.id,
            action_url=f"/listings/{listing.id}/",
            priority="NORMAL",
        )
    )

    return boost


@db_transaction.atomic
def expire_boost(*, boost):
    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing")
        .get(pk=boost.pk)
    )

    if boost.status != ListingBoost.BoostStatus.ACTIVE:
        raise ValidationError("Boost hii haipo active.")

    now = timezone.now()
    if not boost.expires_at:
        raise ValidationError("Boost haina expiry time.")
    if boost.expires_at > now:
        raise ValidationError("Boost bado haija-expire.")

    boost.status = ListingBoost.BoostStatus.EXPIRED
    boost.save(update_fields=["status", "updated_at"])

    listing = Listing.objects.select_for_update().get(pk=boost.listing_id)

    if listing.boosted_until and listing.boosted_until <= now:
        listing.is_boosted = False
        listing.boosted_until = None
        listing.save(update_fields=[
            "is_boosted", "boosted_until", "updated_at",
        ])

    return boost


@db_transaction.atomic
def cancel_boost(*, boost, user):
    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller")
        .get(pk=boost.pk)
    )

    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")

    if not user.is_staff and boost.seller_id != user.id:
        raise ValidationError("Huruhusiwi kufuta boost hii.")

    if boost.status == ListingBoost.BoostStatus.ACTIVE:
        raise ValidationError(
            "Boost active haiwezi kufutwa kupitia endpoint hii."
        )
    if boost.status == ListingBoost.BoostStatus.EXPIRED:
        raise ValidationError("Boost hii tayari ime-expire.")
    if boost.status == ListingBoost.BoostStatus.CANCELLED:
        raise ValidationError("Boost hii tayari ime-cancel.")
    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        raise ValidationError(
            "Boost iliyolipiwa haiwezi ku-cancel bila refund workflow."
        )

    boost.status = ListingBoost.BoostStatus.CANCELLED
    boost.save(update_fields=["status", "updated_at"])
    return boost

# ============================================================================
# PAY BOOST WITH CREDITS
# ============================================================================

@db_transaction.atomic
def pay_boost_with_credits(*, boost, user):
    """
    Pay a boost using one of the user's boost credits instead of cash.
    """
    from apps.credits.services import consume_credit

    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=boost.pk)
    )

    if boost.seller_id != user.id:
        raise ValidationError("Huruhusiwi kulipia boost hii.")

    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        raise ValidationError("Boost hii tayari imelipiwa.")

    if boost.status in [
        ListingBoost.BoostStatus.CANCELLED,
        ListingBoost.BoostStatus.EXPIRED,
    ]:
        raise ValidationError("Boost hii haiwezi kulipiwa.")

    # consume_credit() HAIRUSHI error — inarudisha True/False.
    # Awali jibu lilipuuzwa, kwa hiyo boost ilihesabiwa PAID hata bila credit.
    if not consume_credit(user=user, service_key="boost", required=1):
        raise ValidationError("Hakuna boost credits za kutosha au zimeisha muda.")

    boost.payment_status = ListingBoost.PaymentStatus.PAID
    boost.payment_reference = f"credits_{boost.pk}_{timezone.now().timestamp()}"
    boost.paid_at = timezone.now()
    boost.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])

    return boost


# ============================================================================
# FIMIPAY INTEGRATION
# ============================================================================
from apps.payments.order_ids import make_order_id
from apps.payments.fimipay import (
    create_order as _fp_create_order,
    normalize_payment_method as _fp_normalize_method,
)


# Majina ya field ambazo FimiPay inaweza kutumia kwa URL ya ukurasa wa malipo (kadi / bank).
# Jina halisi bado halijathibitishwa; mstari wa logi "create_order ... keys=" utaonyesha lililo sahihi.
_URL_KEYS = (
    "gateway_url", "payment_url", "checkout_url", "authorization_url",
    "payment_link", "checkout_link", "link", "url",
)
_URL_SKIP_WORDS = ("redirect", "callback", "return", "webhook", "logo", "image")


def _extract_gateway_url(data, *, our_redirect_url=""):
    """Best effort: tafuta URL ya ukurasa wa malipo ya FimiPay kwenye jibu la create_order.

    Haichukui field zinazoonekana kuwa URL YETU ya kurudi (redirect/callback), wala URL ile ile tuliyotuma.
    """
    if not isinstance(data, dict):
        return ""

    def _ok(value):
        return (
            isinstance(value, str)
            and value.startswith(("https://", "http://"))
            and value != our_redirect_url
        )

    for key in _URL_KEYS:
        if _ok(data.get(key)):
            return data[key]
    for key, value in data.items():
        k = str(key).lower()
        if ("url" in k or "link" in k) and not any(w in k for w in _URL_SKIP_WORDS) and _ok(value):
            return value
    return ""


def initiate_boost_payment(*, boost, user, payment_method='mobile', phone=''):
    from apps.payments.fimipay import get_order_status as _fp_get_status

    # ── Phase 1: lock, validate, snapshot (short transaction) ──
    with db_transaction.atomic():
        boost = (
            ListingBoost.objects
            .select_for_update(of=("self",))
            .select_related("listing", "seller", "package")
            .get(pk=boost.pk)
        )
        if boost.seller_id != user.id:
            raise ValidationError("Huruhusiwi kulipia boost hii.")
        if boost.payment_status == ListingBoost.PaymentStatus.PAID:
            raise ValidationError("Boost hii tayari imelipiwa.")

        if not is_boost_fee_enabled():
            raise ValidationError(
                "Ada ya boost imezimwa. Hakuna malipo yanayohitajika."
            )

        if boost.amount <= Decimal("0.00"):
            boost.amount = calculate_boost_fee(package=boost.package)
            boost.save(update_fields=["amount", "updated_at"])

        existing_ref = (boost.payment_reference or "").strip()
        _snapshot = {
            "pk": boost.pk,
            "amount": boost.amount,
            "phone": phone or user.phone or "",
            "email": user.email or "",
            "name": user.name or "",
            "updated_at": boost.updated_at,  # ≈ wakati order ya mwisho ilipoundwa
        }

    method = _fp_normalize_method(payment_method)  # "mobile" | "card" | "bank"

    # Order ya mobile inayosubiri INAWEZA kutumika tena (usimtumie mteja ombi la pili la USSD) lakini tu
    # kama ni changa. Kadi/bank huunda order mpya kila mara: order ya zamani inaweza kuwa ya njia nyingine
    # (hatuhifadhi njia) au ukurasa wake umeachwa, na isingeweza kamwe kuisha ili mteja alipe kwa njia nyingine.
    reuse_window = timedelta(minutes=getattr(settings, "BOOST_REUSE_PENDING_MINUTES", 5))
    reuse_pending = (
        method == "mobile"
        and timezone.now() - _snapshot["updated_at"] <= reuse_window
    )

    # ── Phase 2: HTTP calls (NO lock, NO transaction) ──
    if existing_ref:
        sd = None
        try:
            sd = _fp_get_status(existing_ref)
        except Exception:
            sd = None
        if sd:
            ps = (sd.get("payment_status") or "").upper()
            if ps == "SUCCESS":
                # Tayari imelipwa FimiPay: itumie na uwashe boost sasa
                # (webhook inaweza kuwa imekosa). Errors zinapita juu kwa
                # makusudi — usiunde order ya pili.
                mark_boost_as_paid_from_webhook(
                    ref_id=_snapshot["pk"],
                    payment_reference=sd.get("transid") or existing_ref,
                )
                return sd
            if ps in ("PENDING", "INPROGRESS", "PROCESSING") and reuse_pending:
                return sd

    # Kadi/bank: FimiPay inamrudisha mteja kwenye URL hii baada ya kulipa. Weka kwenye settings, mfano
    # BOOST_PAYMENT_REDIRECT_URL = "https://sokomkononi.co.tz/dashboard/boosts" (bila hiyo, hakuna redirect_url).
    redirect_url = ""
    if method in ("card", "bank"):
        redirect_url = getattr(settings, "BOOST_PAYMENT_REDIRECT_URL", "") or ""

    order_id = make_order_id("BST", _snapshot["pk"])
    data = _fp_create_order(
        order_id=order_id,
        amount=_snapshot["amount"],
        buyer_phone=_snapshot["phone"],
        buyer_email=_snapshot["email"],
        buyer_name=_snapshot["name"],
        payment_method=method,
        redirect_url=redirect_url,
    )

    # Toa URL ya ukurasa wa malipo (kadi/bank) kama `gateway_url`, na andika majina ya field kwenye logi
    # (si thamani) ili uthibitishe jina halisi la FimiPay.
    data = dict(data)
    gateway_url = _extract_gateway_url(data, our_redirect_url=redirect_url)
    logger.info(
        "FimiPay create_order boost=%s method=%s keys=%s gateway_url_found=%s",
        _snapshot["pk"], method, sorted(data.keys()), bool(gateway_url),
    )
    if gateway_url:
        data["gateway_url"] = gateway_url

    # ── Phase 3: re-lock, persist reference ──
    with db_transaction.atomic():
        b = ListingBoost.objects.select_for_update(of=("self",)).get(pk=_snapshot["pk"])
        b.payment_reference = data.get("order_id") or order_id
        b.save(update_fields=["payment_reference", "updated_at"])

    return data


@db_transaction.atomic
def mark_boost_as_paid_from_webhook(*, ref_id, payment_reference):
    boost = (
        ListingBoost.objects
        .select_for_update(of=("self",))
        .select_related("listing", "seller", "package")
        .get(pk=ref_id)
    )
    if boost.payment_status == ListingBoost.PaymentStatus.PAID:
        return boost
    ref = str(payment_reference or "").strip()
    if ref and ListingBoost.objects.filter(payment_reference=ref).exclude(pk=boost.pk).exists():
        raise ValidationError("Payment reference hii tayari imetumika.")
    boost.payment_status = ListingBoost.PaymentStatus.PAID
    boost.payment_reference = payment_reference
    boost.paid_at = timezone.now()
    boost.save(update_fields=[
        "payment_status", "payment_reference", "paid_at", "updated_at",
    ])

    # Activate right away. Without this, a customer who pays and then
    # closes the browser is charged but never boosted, because the
    # frontend is the only other place that calls /activate/.
    # A failure here (e.g. listing no longer AVAILABLE) must not undo
    # the recorded payment, so it is logged and left for review.
    try:
        boost = activate_boost(boost=boost)
    except ValidationError:
        logger.exception(
            "Boost %s paid via webhook but could not be activated", boost.pk,
        )

    return boost

@db_transaction.atomic
def mark_boost_as_refunded(*, ref_id, reason=""):
    boost = ListingBoost.objects.select_for_update().get(pk=ref_id)
    if boost.payment_status == ListingBoost.PaymentStatus.REFUNDED:
        return boost

    boost.payment_status = ListingBoost.PaymentStatus.REFUNDED
    boost.status = ListingBoost.BoostStatus.CANCELLED
    boost.save(update_fields=["payment_status", "status", "updated_at"])

    if boost.listing_id:
        Listing.objects.filter(pk=boost.listing_id).update(
            is_boosted=False, boosted_until=None,
        )
    return boost