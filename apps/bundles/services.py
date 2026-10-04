"""
Bundle purchase flow:
    1. Buyer calls create_purchase(user, bundle)
    2. A BundlePurchase row is created in PENDING
    3. After payment confirmation, mark_purchase_paid() is called
    4. Credits + services are added to the user via apps.credits
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Bundle, BundlePurchase


@transaction.atomic
def create_purchase(*, user, bundle, payment_reference=""):
    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not bundle.active:
        raise ValidationError("Kifurushi hiki hakipo active.")

    existing_pending = BundlePurchase.objects.filter(
        user=user,
        bundle=bundle,
        status=BundlePurchase.Status.PENDING,
    ).first()
    if existing_pending:
        return existing_pending

    try:
        return BundlePurchase.objects.create(
            user=user,
            bundle=bundle,
            amount=bundle.price,
            credits_snapshot=bundle.credits,
            services_snapshot=bundle.services,
            status=BundlePurchase.Status.PENDING,
            payment_reference=(payment_reference or "").strip() or None,
        )
    except IntegrityError:
        # Concurrent create — fetch the winner.
        return BundlePurchase.objects.get(
            user=user,
            bundle=bundle,
            status=BundlePurchase.Status.PENDING,
        )


@transaction.atomic
def mark_purchase_paid(*, purchase, payment_reference=""):
    purchase = (
        BundlePurchase.objects
        .select_for_update()
        .select_related("bundle")
        .get(pk=purchase.pk)
    )

    if (purchase.status == BundlePurchase.Status.PAID
            and purchase.payment_reference == (payment_reference or "").strip()):
        return purchase

    if purchase.status == BundlePurchase.Status.PAID:
        raise ValidationError("Purchase hii tayari imelipiwa.")

    if purchase.status in (
        BundlePurchase.Status.FAILED,
        BundlePurchase.Status.REFUNDED,
    ):
        raise ValidationError("Purchase hii haiwezi kulipiwa.")

    now = timezone.now()
    expires_at = now + timedelta(days=purchase.bundle.validity_days)

    ref = (payment_reference or "").strip()
    if ref and BundlePurchase.objects.filter(
        payment_reference=ref,
    ).exclude(pk=purchase.pk).exists():
        raise ValidationError(
            "Payment reference hii tayari imetumika."
        )
    if ref:
        purchase.payment_reference = ref
    purchase.status = BundlePurchase.Status.PAID
    purchase.paid_at = now
    purchase.expires_at = expires_at
    purchase.save(update_fields=[
        "status", "payment_reference", "paid_at", "expires_at",
    ])

    from apps.credits.services import grant_bundle_credits
    grant_bundle_credits(
        user=purchase.user,
        credits=purchase.credits_snapshot or {},
        services=purchase.services_snapshot or [],
        expires_at=expires_at,
        bundle_code=purchase.bundle.code,
        bundle_name=purchase.bundle.name_sw,
    )

    return purchase


# ============================================================================
# FIMIPAY INTEGRATION
# ============================================================================
from apps.payments.fimipay import (
    create_order as _fp_create_order,
    normalize_payment_method as _fp_normalize_method,
)
from apps.payments.order_ids import make_order_id


@transaction.atomic
def initiate_purchase_payment(*, purchase, user, payment_method='mobile', phone=''):
    if purchase.user_id != user.id:
        raise ValidationError("Huruhusiwi kulipia ununuzi huu.")
    from apps.payments.fimipay import get_order_status as _fp_get_status

    existing_ref = (purchase.payment_reference or "").strip()
    if existing_ref:
        try:
            sd = _fp_get_status(existing_ref)
            if (sd.get("payment_status") or "").upper() in ("PENDING", "INPROGRESS", "SUCCESS"):
                return sd
        except Exception:
            pass

    # FIX: FimiPay rejects an order_id it has seen before, so every new
    # attempt gets a unique id (BND-<pk>-<random>). The webhook parses the pk.
    order_id = make_order_id("BND", purchase.pk)
    data = _fp_create_order(
        order_id=order_id,
        amount=purchase.amount,
        buyer_phone=phone or user.phone or "",
        buyer_email=user.email or "",
        buyer_name=user.name or "",
        payment_method=_fp_normalize_method(payment_method),
    )
    purchase.payment_reference = data.get("order_id") or order_id
    purchase.save(update_fields=["payment_reference"])
    return data


@transaction.atomic
def mark_purchase_paid_from_webhook(*, ref_id, payment_reference):
    purchase = (
        BundlePurchase.objects
        .select_for_update()
        .select_related("bundle")
        .get(pk=ref_id)
    )
    if purchase.status == BundlePurchase.Status.PAID:
        return purchase

    now = timezone.now()
    expires_at = now + timedelta(days=purchase.bundle.validity_days)
    purchase.status = BundlePurchase.Status.PAID
    purchase.payment_reference = payment_reference
    purchase.paid_at = now
    purchase.expires_at = expires_at
    purchase.save(update_fields=[
        "status", "payment_reference", "paid_at", "expires_at",
    ])
    from apps.credits.services import grant_bundle_credits
    grant_bundle_credits(
        user=purchase.user,
        credits=purchase.credits_snapshot or {},
        services=purchase.services_snapshot or [],
        expires_at=expires_at,
        bundle_code=purchase.bundle.code,
        bundle_name=purchase.bundle.name_sw,
    )
    return purchase