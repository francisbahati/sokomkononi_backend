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

    # Prevent duplicate open PENDING for the same (user, bundle).
    existing_pending = (
        BundlePurchase.objects
        .select_for_update()
        .filter(
            user=user,
            bundle=bundle,
            status=BundlePurchase.Status.PENDING,
        )
        .first()
    )
    if existing_pending:
        return existing_pending

    return BundlePurchase.objects.create(
        user=user,
        bundle=bundle,
        amount=bundle.price,
        credits_snapshot=bundle.credits,
        services_snapshot=bundle.services,
        status=BundlePurchase.Status.PENDING,
        payment_reference=(payment_reference or "").strip() or None,
    )


@transaction.atomic
def mark_purchase_paid(*, purchase, payment_reference=""):
    purchase = (
        BundlePurchase.objects
        .select_for_update()
        .select_related("bundle")
        .get(pk=purchase.pk)
    )

    # Idempotent retry: same reference → return existing.
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
