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

from django.core.exceptions import ObjectDoesNotExist
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
}

OK = "ok"
IGNORED = "ignored"   # permanent: retrying will not help
RETRY = "retry"       # transient: ask FimiPay to send it again


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

    module_path, func_name = target
    try:
        handler = getattr(importlib.import_module(module_path), func_name)
        handler(
            ref_id=ref_id_int,
            payment_reference=event.get("transid") or order_id,
        )
    except (ObjectDoesNotExist, ValidationError):
        logger.exception(
            "Webhook rejected for order_id=%s (needs manual review)", order_id,
        )
        return IGNORED
    except Exception:
        logger.exception(
            "Webhook routing failed for order_id=%s (will retry)", order_id,
        )
        return RETRY
    return OK


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
        "FimiPay webhook: event=%s order_id=%s status=%s",
        event, order_id, payment_status,
    )

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

    return JsonResponse({"received": True}, status=200)