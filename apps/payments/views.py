"""
FimiPay webhook receiver.

POST /api/payments/webhook/
Verifies X-Fimipay-Signature (HMAC-SHA256 of raw body).
Idempotent — safe to receive the same event twice.
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .fimipay import verify_webhook_signature

logger = logging.getLogger(__name__)


def _route_success(order_id, event):
    """Route a SUCCESS webhook to the right SokoMkononi service."""
    if not order_id:
        return False

    from apps.listings.services.listing_payment import (
        mark_listing_fee_as_paid_from_webhook,
    )
    from apps.boosting.services.boost import mark_boost_as_paid_from_webhook
    from apps.bundles.services import mark_purchase_paid_from_webhook
    from apps.leading_fees.services.leading import mark_leading_paid_from_webhook
    from apps.banners.services import mark_banner_paid_from_webhook

    prefix, _, ref_id = order_id.partition("-")
    ref_id_int = int(ref_id) if ref_id.isdigit() else None
    if ref_id_int is None:
        logger.warning("Webhook order_id has bad ref: %s", order_id)
        return False

    try:
        if prefix == "LSF":
            mark_listing_fee_as_paid_from_webhook(
                ref_id=ref_id_int,
                payment_reference=event.get("transid") or order_id,
            )
        elif prefix == "BST":
            mark_boost_as_paid_from_webhook(
                ref_id=ref_id_int,
                payment_reference=event.get("transid") or order_id,
            )
        elif prefix == "LDS":
            mark_leading_paid_from_webhook(
                ref_id=ref_id_int,
                payment_reference=event.get("transid") or order_id,
            )
        elif prefix == "BND":
            mark_purchase_paid_from_webhook(
                ref_id=ref_id_int,
                payment_reference=event.get("transid") or order_id,
            )
        elif prefix == "ADV":
            mark_banner_paid_from_webhook(
                ref_id=ref_id_int,
                payment_reference=event.get("transid") or order_id,
            )
        else:
            logger.info("Unknown webhook prefix: %s", prefix)
            return False
    except Exception:
        logger.exception("Webhook routing failed for order_id=%s", order_id)
        return False
    return True


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

    event = payload.get("event") or ""
    order_id = payload.get("order_id")
    payment_status = payload.get("payment_status") or payload.get("status")

    logger.info(
        "FimiPay webhook: event=%s order_id=%s status=%s",
        event, order_id, payment_status,
    )

    success = event == "payment.success" or payment_status == "SUCCESS"
    if success and order_id:
        _route_success(order_id, {
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "transid": payload.get("transid"),
            "channel": payload.get("channel"),
        })

    return JsonResponse({"received": True}, status=200)
