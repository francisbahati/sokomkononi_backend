"""TOTP 2FA helpers."""
import secrets

import pyotp
from django.contrib.auth.hashers import make_password, check_password

from .models import UserTOTP


def get_or_create_totp(user):
    obj, _ = UserTOTP.objects.get_or_create(user=user)
    if not obj.secret:
        obj.secret = pyotp.random_base32()
        obj.save(update_fields=["secret"])
    return obj


def build_provisioning_uri(user):
    t = get_or_create_totp(user)
    return pyotp.TOTP(t.secret).provisioning_uri(
        name=user.email or str(user.pk),
        issuer_name="SokoMkononi",
    )


def verify_totp(user, code):
    t = get_or_create_totp(user)
    if not t.enabled:
        return False
    return pyotp.TOTP(t.secret).verify(str(code or "").strip(), valid_window=1)


def generate_recovery_codes(user, count=10):
    t = get_or_create_totp(user)
    plain = [secrets.token_hex(5).upper() for _ in range(count)]
    t.recovery_codes = [make_password(c) for c in plain]
    t.save(update_fields=["recovery_codes"])
    return plain


def verify_recovery_code(user, code):
    t = get_or_create_totp(user)
    code = str(code or "").strip().upper()
    for hashed in list(t.recovery_codes or []):
        if check_password(code, hashed):
            t.recovery_codes = [h for h in t.recovery_codes if h != hashed]
            t.save(update_fields=["recovery_codes"])
            return True
    return False
