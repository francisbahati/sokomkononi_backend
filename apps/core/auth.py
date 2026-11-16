# apps/core/auth.py
"""
Authentication classes zenye ulinzi wa jumla wa 2FA kwa staff (angalia
`guard_staff_write` kwenye apps/core/admin_2fa.py).

MUHIMU: DRF inatumia authenticator ya KWANZA inayorudisha mtumiaji; zinazofuata
hazifikiwi. Kwa hiyo ulinzi lazima uwe KWENYE class inayotumika kwanza — usiiweke
kama class ya pili kwenye DEFAULT_AUTHENTICATION_CLASSES.

settings.py:

    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.core.auth.Admin2FAFlexibleJWTAuthentication",
    ),
"""
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.authentication import FlexibleJWTAuthentication

from .admin_2fa import Admin2FAGuardMixin


class Admin2FAFlexibleJWTAuthentication(Admin2FAGuardMixin, FlexibleJWTAuthentication):
    """FlexibleJWTAuthentication ya mradi + ulinzi wa 2FA kwa staff."""


class Admin2FAJWTAuthentication(Admin2FAGuardMixin, JWTAuthentication):
    """JWTAuthentication ya kawaida + ulinzi (kwa miradi isiyo na Flexible)."""
