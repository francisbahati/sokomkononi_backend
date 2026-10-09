"""
Credits service helpers — kutumia credits za bundles kwa huduma mbalimbali.

Bundle inatoa credits kwa service_key (mfano "boost", "listing", "leading",
"ads", "reservation", "success"). User anaweza kutumia credit moja kwa
kila huduma badala ya kulipa kwa FimiPay.
"""
from django.db import transaction
from django.utils import timezone

from .models import UserCredit, UserService


def has_service(user, service_key):
    """
    Angalia kama user ana service active (mfano boost inayoendelea).
    Hii ilikuwa kwenye views.py ya awali — tumeihamisha hapa ili
    services.py iwe single source of truth.
    """
    if not user or not user.is_authenticated:
        return False
    obj = UserService.objects.filter(
        user=user, service_key=service_key,
    ).first()
    if not obj:
        return False
    if obj.expires_at and obj.expires_at < timezone.now():
        return False
    return True


def get_user_credits(user):
    """Rudisha dict ya {service_key: remaining} kwa user."""
    if not user or not user.is_authenticated:
        return {}
    rows = UserCredit.objects.filter(user=user)
    return {r.service_key: r.remaining for r in rows}


def has_credit(user, service_key, required=1):
    """Angalia kama user ana credit ya kutosha ya service_key."""
    if not user or not user.is_authenticated:
        return False
    try:
        credit = UserCredit.objects.get(user=user, service_key=service_key)
    except UserCredit.DoesNotExist:
        return False
    if credit.expires_at and credit.expires_at < timezone.now():
        return False
    return credit.remaining >= required


@transaction.atomic
def consume_credit(user, service_key, required=1):
    """
    Consume credit moja (au `required`) ya service_key kwa user.

    Returns:
        True  — kama ilifanikiwa
        False — kama hana credit ya kutosha au imeisha muda
    """
    if not user or not user.is_authenticated:
        return False
    if required < 1:
        return True

    try:
        credit = (
            UserCredit.objects
            .select_for_update()
            .get(user=user, service_key=service_key)
        )
    except UserCredit.DoesNotExist:
        return False

    if credit.expires_at and credit.expires_at < timezone.now():
        return False

    if credit.remaining < required:
        return False

    credit.remaining -= required
    credit.save(update_fields=["remaining", "updated_at"])
    return True

@transaction.atomic
def grant_bundle_credits(
    *,
    user,
    credits,
    services,
    expires_at=None,
    bundle_code="",
    bundle_name="",
):
    """
    Apply a bundle's credits + services to a user.

    `credits` is a dict like {"listing": 5, "boost": 2, "ads": 1}.
    `services` is a list of service keys to grant for the bundle window.
    """
    for key, qty in (credits or {}).items():
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue

        uc, _ = UserCredit.objects.select_for_update().get_or_create(
            user=user,
            service_key=key,
            defaults={"remaining": 0, "total": 0},
        )
        uc.remaining += qty
        uc.total += qty
        if expires_at:
            candidates = [d for d in (uc.expires_at, expires_at) if d]
            if candidates:
                uc.expires_at = max(candidates)
        uc.last_bundle_code = bundle_code
        uc.last_bundle_name = bundle_name
        uc.save()

    for key in (services or []):
        UserService.objects.update_or_create(
            user=user,
            service_key=key,
            defaults={"expires_at": expires_at},
        )
