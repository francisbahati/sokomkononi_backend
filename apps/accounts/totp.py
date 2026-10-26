"""TOTP 2FA helpers."""
import secrets

import pyotp
from django.contrib.auth.hashers import make_password, check_password
from django.core.cache import cache

from .models import UserTOTP

MAX_FAILS = 5          # majaribio yaliyoshindwa kabla ya lock
LOCK_SECONDS = 600     # lock ya dakika 10


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


def verify_totp(user, code, require_enabled=True):
    """
    require_enabled=False inatumika wakati wa setup (kabla 2FA haijawashwa)
    ili kuthibitisha code ya kwanza.
    Pia inazuia code ile ile kutumika mara mbili (replay) ndani ya ~90s.
    """
    t = get_or_create_totp(user)
    if require_enabled and not t.enabled:
        return False
    code = str(code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    if not pyotp.TOTP(t.secret).verify(code, valid_window=1):
        return False
    if not cache.add(f"totp-used:{user.pk}:{code}", 1, 90):
        return False  # code hii imeshatumika
    return True


def generate_recovery_codes(user, count=10):
    t = get_or_create_totp(user)
    plain = [secrets.token_hex(5).upper() for _ in range(count)]
    t.recovery_codes = [make_password(c) for c in plain]
    t.save(update_fields=["recovery_codes"])
    return plain


def verify_recovery_code(user, code):
    t = get_or_create_totp(user)
    code = str(code or "").strip().replace("-", "").replace(" ", "").upper()
    if not code:
        return False
    for hashed in list(t.recovery_codes or []):
        if check_password(code, hashed):
            t.recovery_codes = [h for h in t.recovery_codes if h != hashed]
            t.save(update_fields=["recovery_codes"])
            return True
    return False


# ------------------------------------------------------------
# Rate limit ya majaribio ya code (per user)
# ------------------------------------------------------------
def _fail_key(user):
    return f"2fa-fail:{user.pk}"


def is_locked(user):
    return (cache.get(_fail_key(user)) or 0) >= MAX_FAILS


def register_failure(user):
    key = _fail_key(user)
    cache.add(key, 0, LOCK_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOCK_SECONDS)


def clear_failures(user):
    cache.delete(_fail_key(user))