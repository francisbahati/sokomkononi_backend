"""
Credit + service management. Called by bundle purchases and by
service-consumption flows (boost, leading, listing, ads, etc.).
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import UserCredit, UserService


@transaction.atomic
def grant_bundle_credits(*, user, credits, services, expires_at,
                         bundle_code="", bundle_name=""):
    """
    Add credits and services to a user from a bundle purchase.

    `credits` can be:
        - an int     → applied to service_key == bundle.type
        - a dict     → { "listing": 10, "boost": 3, ... }
    """
    if isinstance(credits, int):
        credits = {"default": credits}

    for service_key, amount in (credits or {}).items():
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue

        obj, _ = UserCredit.objects.select_for_update().get_or_create(
            user=user,
            service_key=service_key,
            defaults={"remaining": 0, "total": 0},
        )
        obj.remaining += amount
        obj.total += amount
        if expires_at and (not obj.expires_at or expires_at > obj.expires_at):
            obj.expires_at = expires_at
        if bundle_code:
            obj.last_bundle_code = bundle_code
        if bundle_name:
            obj.last_bundle_name = bundle_name
        obj.save()

    for service_key in (services or []):
        obj, _ = UserService.objects.get_or_create(
            user=user,
            service_key=service_key,
            defaults={"expires_at": expires_at},
        )
        if expires_at and (not obj.expires_at or expires_at > obj.expires_at):
            obj.expires_at = expires_at
            obj.save(update_fields=["expires_at"])


def get_credit(user, service_key):
    """Return the UserCredit row for a user+service, or None."""
    if not user or not user.is_authenticated:
        return None
    return UserCredit.objects.filter(
        user=user, service_key=service_key,
    ).first()


def has_credit(user, service_key, amount=1):
    credit = get_credit(user, service_key)
    if not credit:
        return False
    if credit.expires_at and credit.expires_at < timezone.now():
        return False
    return credit.remaining >= amount


@transaction.atomic
def consume_credit(*, user, service_key, amount=1):
    credit = (
        UserCredit.objects
        .select_for_update()
        .filter(user=user, service_key=service_key)
        .first()
    )
    if not credit:
        raise ValidationError(
            f"Hakuna credit ya {service_key}."
        )
    if credit.expires_at and credit.expires_at < timezone.now():
        raise ValidationError(f"Credit ya {service_key} imeisha muda.")
    if credit.remaining < amount:
        raise ValidationError(
            f"Credit ya {service_key} haitoshi ({credit.remaining} imebaki)."
        )
    credit.remaining -= amount
    credit.save(update_fields=["remaining", "updated_at"])
    return credit


def has_service(user, service_key):
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
