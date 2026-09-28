"""
FimiPay API client for SokoMkononi.
Base URL: https://fimipay.com/api/v1
Auth: Bearer sk_test_* (sandbox) or sk_live_* (production)
"""
import hashlib
import hmac
import logging
from decimal import Decimal

import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _resolve_test_outcome():
    """
    Read the SOKO_FIMIPAY_TEST_OUTCOME env var (default empty).
    When set to 'success', every create_order in test mode
    immediately succeeds — perfect for end-to-end QA.
    """
    import os
    return os.environ.get("SOKO_FIMIPAY_TEST_OUTCOME", "").strip() or None
REQUEST_TIMEOUT = 30


def _headers():
    if not settings.FIMIPAY_SECRET_KEY:
        raise ValidationError("FIMIPAY_SECRET_KEY haijawekwa kwenye .env.")
    return {
        "Authorization": f"Bearer {settings.FIMIPAY_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "SokoMkononi-SDK/1.0",
    }


def _post(path, payload):
    url = f"{settings.FIMIPAY_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = requests.post(
            url, json=payload, headers=_headers(), timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.exception("FimiPay request failed: %s", url)
        raise ValidationError("Imeshindwa kuwasiliana na FimiPay.") from exc

    try:
        data = response.json()
    except ValueError:
        raise ValidationError("Jibu la FimiPay si sahihi (si JSON).")

    if not response.ok:
        message = data.get("message") or data.get("error") or f"FimiPay error ({response.status_code})"
        logger.warning("FimiPay error %s: %s", response.status_code, message)
        raise ValidationError(message)
    return data


def _get(path):
    url = f"{settings.FIMIPAY_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.exception("FimiPay GET failed: %s", url)
        raise ValidationError("Imeshindwa kuwasiliana na FimiPay.") from exc

    try:
        data = response.json()
    except ValueError:
        raise ValidationError("Jibu la FimiPay si sahihi.")

    if not response.ok:
        raise ValidationError(data.get("message") or "FimiPay error.")
    return data


def create_order(*, order_id, amount, buyer_phone, buyer_email="", buyer_name="",
                 currency=None, payment_method="mobile", redirect_url="", test_outcome=None):
    if not order_id:
        raise ValidationError({"order_id": "order_id inahitajika."})

    payload = {
        "order_id": str(order_id)[:64],
        "amount": int(Decimal(str(amount))),
        "buyer_phone": str(buyer_phone),
        "payment_method": payment_method,
        "currency": currency or settings.FIMIPAY_CURRENCY,
    }
    if buyer_email:
        payload["buyer_email"] = buyer_email
    if buyer_name:
        payload["buyer_name"] = buyer_name
    if redirect_url:
        payload["redirect_url"] = redirect_url
    # Allow env-var override for automated QA.
    resolved_outcome = test_outcome or _resolve_test_outcome()
    if resolved_outcome and settings.FIMIPAY_SECRET_KEY.startswith("sk_test_"):
        payload["test_outcome"] = resolved_outcome

    response = _post("/payment/create_order", payload)
    data = response.get("data") or {}
    if not data.get("order_id"):
        raise ValidationError("FimiPay hakurudisha order_id.")
    return data


def get_order_status(order_id):
    response = _post("/payment/order_status", {"order_id": str(order_id)})
    return response.get("data") or {}


def list_transactions():
    response = _post("/transactions/readbyId", {})
    return response.get("data") or []


def create_payout(*, amount, method, account_number, account_name=""):
    payload = {
        "amount": int(Decimal(str(amount))),
        "method": method,
        "account_number": str(account_number),
    }
    if account_name:
        payload["account_name"] = account_name
    response = _post("/payouts/create", payload)
    return response.get("data") or {}


def get_payout_status(withdrawal_id):
    response = _get(f"/payouts/status/{withdrawal_id}")
    return response.get("data") or response


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    if not settings.FIMIPAY_WEBHOOK_SECRET:
        logger.error("FIMIPAY_WEBHOOK_SECRET haijawekwa — webhook imekataliwa.")
        return False
    expected = hmac.new(
        settings.FIMIPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())
