"""
Bundle purchase flow:
    1. Buyer calls create_purchase(user, bundle)
    2. A BundlePurchase row is created in PENDING
    3. After payment confirmation, mark_purchase_paid() is called
    4. Credits + services are added to the user via apps.credits
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Bundle, BundlePurchase


@transaction.atomic
def create_purchase(*, user, bundle, payment_reference=""):
    if not user or not user.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not bundle.active:
        raise ValidationError("Kifurushi hiki hakipo active.")

    purchase = BundlePurchase.objects.create(
        user=user,
        bundle=bundle,
        amount=bundle.price,
        credits_snapshot=bundle.credits,
        services_snapshot=bundle.services,
        status=BundlePurchase.Status.PENDING,
        payment_reference=(payment_reference or "").strip() or None,
    )
    return purchase


@transaction.atomic
def mark_purchase_paid(*, purchase, payment_reference=""):
    if purchase.status == BundlePurchase.Status.PAID:
        return purchase

    now = timezone.now()
    expires_at = now + timedelta(days=purchase.bundle.validity_days)

    if payment_reference:
        purchase.payment_reference = payment_reference.strip()
    purchase.status = BundlePurchase.Status.PAID
    purchase.paid_at = now
    purchase.expires_at = expires_at
    purchase.save(update_fields=[
        "status", "payment_reference", "paid_at", "expires_at",
    ])

    # Grant credits + services
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
