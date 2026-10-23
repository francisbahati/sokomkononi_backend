"""
FimiPay webhook receiver.

POST /api/payments/webhook/
Verifies X-Fimipay-Signature (HMAC-SHA256 of raw body).

Handlers must be idempotent: the same event can arrive more than once,
and transient failures are answered with HTTP 500 so FimiPay can retry.
"""
import importlib
import json
import logging
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import ProgrammingError, IntegrityError, DataError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import ValidationError

from .fimipay import verify_webhook_signature
from .order_ids import parse_order_id

logger = logging.getLogger(__name__)


# order_id prefix -> (module, function).
# Imported lazily, so a broken import in one app cannot take down the
# webhook for every other payment type.
_SUCCESS_HANDLERS = {
    "LSF": (
        "apps.listings.services.listing_payment",
        "mark_listing_fee_as_paid_from_webhook",
    ),
    "BST": (
        "apps.boosting.services.boost",
        "mark_boost_as_paid_from_webhook",
    ),
    "LDS": (
        "apps.leading_fees.services.leading",
        "mark_leading_paid_from_webhook",
    ),
    "BND": (
        "apps.bundles.services",
        "mark_purchase_paid_from_webhook",
    ),
    "ADV": (
        "apps.banners.services",
        "mark_banner_paid_from_webhook",
    ),
    "SFE": (
        "apps.finance.services_success_fee",
        "mark_success_fee_paid_from_webhook",
    ),
    "RSV": (
        "apps.transactions.services.reservation",
        "mark_reservation_paid_from_webhook",
    ),
    # Ada ya kuongeza muda wa reservation
    "RSX": (
        "apps.transactions.services.reservation",
        "mark_extension_paid_from_webhook",
    ),
}

OK = "ok"
IGNORED = "ignored"   # permanent: retrying will not help
RETRY = "retry"       # transient: ask FimiPay to send it again




# Refund handlers — route FimiPay refund events to the right service
_REFUND_HANDLERS = {
    "LSF": ("apps.listings.services.listing_payment", "mark_listing_fee_as_refunded"),
    "BST": ("apps.boosting.services.boost", "mark_boost_as_refunded"),
    "LDS": ("apps.leading_fees.services.leading", "mark_leading_as_refunded"),
    "BND": ("apps.bundles.services", "mark_purchase_as_refunded"),
    "ADV": ("apps.banners.services", "mark_banner_as_refunded"),
    "SFE": ("apps.finance.services_success_fee", "mark_success_fee_as_refunded"),
    "RSV": ("apps.transactions.services.reservation", "mark_reservation_as_refunded"),
    "RSX": ("apps.transactions.services.reservation", "mark_extension_as_refunded"),
    "REF": ("apps.payments.refunds", "mark_refund_completed_from_webhook"),
}


def _route_refund(order_id, event):
    if not order_id:
        return IGNORED
    try:
        prefix, ref_id_int = parse_order_id(order_id)
    except (ValueError, TypeError):
        return IGNORED
    if ref_id_int is None:
        return IGNORED
    target = _REFUND_HANDLERS.get(prefix)
    if not target:
        logger.warning("Refund for unknown prefix %r order=%s", prefix, order_id)
        return IGNORED
    module_path, func_name = target
    try:
        handler = getattr(importlib.import_module(module_path), func_name)
        handler(ref_id=ref_id_int, reason=event.get("reason", ""))
    except ObjectDoesNotExist:
        return IGNORED
    except Exception:
        logger.exception("Refund routing failed for %s", order_id)
        return RETRY
    return OK


def _verify_amount(prefix, ref_id_int, reported_amount, order_id, event=None):
    from .models import WebhookDiscrepancy
    """
    Compare FimiPay-reported amount against the DB-stored amount.

    Returns True if EXACTLY equal, False otherwise.
    Over- and under-payments both return False and are logged loudly.
    """
    if reported_amount is None:
        WebhookDiscrepancy.objects.create(
            order_id=order_id, prefix=prefix, ref_id=ref_id_int,
            reason="missing_amount", raw_payload=event or {},
        )
        logger.error("Webhook missing amount for order_id=%s", order_id)
        return False

    try:
        reported = Decimal(str(reported_amount)).quantize(Decimal("0.01"))
    except Exception:
        logger.error(
            "Webhook non-numeric amount for order_id=%s: %r",
            order_id, reported_amount,
        )
        return False

    expected = _lookup_expected_amount(prefix, ref_id_int)
    if expected is None:
        WebhookDiscrepancy.objects.create(
            order_id=order_id, prefix=prefix, ref_id=ref_id_int,
            reason="no_db_record", raw_payload=event or {},
        )
        logger.error(
            "Webhook: no DB record for order_id=%s (prefix=%s, ref=%s)",
            order_id, prefix, ref_id_int,
        )
        return False

    expected = Decimal(str(expected)).quantize(Decimal("0.01"))

    if reported != expected:
        direction = "UNDERPAYMENT" if reported < expected else "OVERPAYMENT"
        WebhookDiscrepancy.objects.create(
            order_id=order_id, prefix=prefix, ref_id=ref_id_int,
            expected_amount=expected, reported_amount=reported,
            reason="amount_mismatch", raw_payload=event or {},
        )
        logger.error(
            "%s order_id=%s expected=%s reported=%s",
            direction, order_id, expected, reported,
        )
        return False
    return True


def _lookup_expected_amount(prefix, ref_id_int):
    """Fetch the DB-stored amount for the given order prefix + ref.

    Returns the amount (Decimal) or None if no record exists.
    Re-raises on unexpected errors so the webhook retries.
    """
    from django.core.exceptions import ObjectDoesNotExist
    try:
        if prefix == "LSF":
            from apps.listings.models import ListingFee
            # order_id "LSF-<listing_id>-xxxx" ina ID ya LISTING, si ya ListingFee.
            # (Awali ilitumia pk=ref_id_int -> ilitafuta fee ya listing nyingine
            # au haikupatikana kabisa, na malipo yalikataliwa kimya kimya.)
            return ListingFee.objects.get(listing_id=ref_id_int).amount
        if prefix == "BST":
            from apps.boosting.models import ListingBoost
            return ListingBoost.objects.get(pk=ref_id_int).amount
        if prefix == "LDS":
            from apps.leading_fees.models import ListingLeading
            return ListingLeading.objects.get(pk=ref_id_int).price
        if prefix == "BND":
            from apps.bundles.models import BundlePurchase
            return BundlePurchase.objects.get(pk=ref_id_int).amount
        if prefix == "ADV":
            from apps.banners.models import BannerAd
            return BannerAd.objects.get(pk=ref_id_int).amount
        if prefix == "SFE":
            from apps.finance.models import SuccessFeePayment
            return SuccessFeePayment.objects.get(pk=ref_id_int).amount
        if prefix == "RSV":
            from apps.transactions.models import Reservation
            return Reservation.objects.get(pk=ref_id_int).deposit_amount
        if prefix == "RSX":
            from apps.transactions.models import ReservationExtension
            return ReservationExtension.objects.get(pk=ref_id_int).fee
    except ObjectDoesNotExist:
        return None
    except Exception:
        logger.exception("Amount lookup failed for %s-%s", prefix, ref_id_int)
        raise
    return None


def _route_success(order_id, event):
    """Route a SUCCESS webhook to the right SokoMkononi service."""
    if not order_id:
        return IGNORED

    # Accepts both "BND-5" (old) and "BND-5-a1b2c3d4" (unique per attempt).
    try:
        prefix, ref_id_int = parse_order_id(order_id)
    except (ValueError, TypeError):
        logger.warning("Webhook order_id is malformed: %s", order_id)
        return IGNORED

    if ref_id_int is None:
        logger.warning("Webhook order_id has bad ref: %s", order_id)
        return IGNORED

    target = _SUCCESS_HANDLERS.get(prefix)
    if not target:
        # A paid order nobody handles: make it visible in the logs.
        logger.warning(
            "Unknown webhook prefix %r (order_id=%s) - payment NOT applied",
            prefix, order_id,
        )
        return IGNORED

    if not _verify_amount(prefix, ref_id_int, event.get("amount"), order_id):
        logger.error(
            "Webhook REJECTED for order_id=%s (amount mismatch)", order_id,
        )
        return IGNORED

    return _call_success_handler(
        order_id, target, ref_id_int, event.get("transid") or order_id,
    )


def _call_success_handler(order_id, target, ref_id_int, payment_reference):
    module_path, func_name = target
    try:
        handler = getattr(importlib.import_module(module_path), func_name)
        handler(
            ref_id=ref_id_int,
            payment_reference=payment_reference,
        )
    except ObjectDoesNotExist:
        logger.exception("Webhook: record missing for %s", order_id)
        return IGNORED
    except ValidationError:
        logger.exception("Webhook: retryable error for %s", order_id)
        return RETRY
    except (ProgrammingError, IntegrityError, DataError) as exc:
        # Permanent — schema drift / constraint violation.
        logger.exception(
            "Webhook PERMANENT failure for %s (%s): %s",
            order_id, type(exc).__name__, exc,
        )
        return IGNORED
    except Exception:
        logger.exception(
            "Webhook routing failed for order_id=%s (will retry)", order_id,
        )
        return RETRY
    return OK


def apply_success_from_status(order_id, data):
    """
    PULL reconciliation: inaitwa na order_status_view pale FimiPay inasema
    SUCCESS (jibu la server-to-server kwa kutumia secret key yetu), ili
    malipo yatumike hata kama webhook haikufika au ilikataliwa.

    Handlers ni idempotent, kwa hiyo kuita mara nyingi ni salama.
    Inarudisha OK / IGNORED / RETRY.
    """
    try:
        prefix, ref_id_int = parse_order_id(order_id)
    except (ValueError, TypeError):
        return IGNORED
    if ref_id_int is None:
        return IGNORED

    target = _SUCCESS_HANDLERS.get(prefix)
    if not target:
        return IGNORED

    data = data or {}
    logger.info(
        "Reconcile-from-poll: applying SUCCESS for order_id=%s", order_id,
    )
    return _call_success_handler(
        order_id, target, ref_id_int,
        data.get("transid") or order_id,
    )


@csrf_exempt
def fimipay_webhook(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)

    raw_body = request.body
    signature = request.headers.get("X-Fimipay-Signature", "")

    if not verify_webhook_signature(raw_body, signature):
        logger.warning("FimiPay webhook: invalid signature")
        return JsonResponse({"detail": "Invalid signature."}, status=401)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Invalid payload."}, status=400)

    event = payload.get("event") or ""
    order_id = payload.get("order_id")
    payment_status = str(
        payload.get("payment_status") or payload.get("status") or ""
    ).upper()

    logger.info(
        "FimiPay webhook: event=%s order_id=%s status=%s keys=%s",
        event, order_id, payment_status, sorted(payload.keys()),
    )

    if event == "payment.refunded" or payment_status == "REFUNDED":
        result = _route_refund(order_id, {"reason": payload.get("reason", "")})
        if result == RETRY:
            return JsonResponse({"detail": "Retry"}, status=500)
        return JsonResponse({"received": True}, status=200)

    success = event == "payment.success" or payment_status == "SUCCESS"
    if success and order_id:
        result = _route_success(order_id, {
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "transid": payload.get("transid"),
            "channel": payload.get("channel"),
        })
        if result == RETRY:
            return JsonResponse(
                {"detail": "Temporary error, please retry."}, status=500,
            )
        if result == IGNORED:
            logger.error(
                "PAID BUT NOT APPLIED: order_id=%s amount=%s transid=%s "
                "(see WebhookDiscrepancy / run reconcile_payments)",
                order_id, payload.get("amount"), payload.get("transid"),
            )

    return JsonResponse({"received": True}, status=200)