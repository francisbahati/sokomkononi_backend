# apps/core/admin_2fa.py
"""
Admin 2FA enforcement.

Akaunti za staff/admin zinaweza kutumia API za admin TU zikiwa na 2FA
(TOTP) iliyowashwa. Admin asiye na 2FA bado anaweza kuingia na kutumia
endpoints za kawaida (/auth/me/, /auth/profile/, /auth/2fa/*) ili kuiwasha,
lakini kila endpoint iliyolindwa na `IsAdminWith2FA` (au `IsAdminUser` /
`IsSuperUser` / `IsAdminOrReadOnly` za apps.core.permissions) inakataa kwa
403 yenye code `ADMIN_2FA_REQUIRED` hadi aiwashe.

Settings (zote za hiari):
  ADMIN_REQUIRE_2FA = True                  # zima kabisa kwa dharura: False
  ADMIN_2FA_GUARD_READS = False             # True = staff asiye na 2FA hawezi hata
                                            # kusoma (nje ya endpoints za auth)
  ADMIN_2FA_ENFORCE_TOKEN_CLAIM = False     # True = token lazima iwe na claim
                                            # `mfa` (imewekwa baada ya code ya
                                            # 2FA). Inazuia kupita 2FA kwa njia
                                            # zingine za kupata token (mf. social
                                            # login). Washa baada ya kuthibitisha
                                            # `request.auth` ni JWT kwenye mfumo
                                            # wako; admin walioingia kabla ya
                                            # hapo wataingia tena mara moja.
"""
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

MFA_CLAIM = "mfa"
_UNSET = object()
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

# Endpoints ambazo staff asiye na 2FA bado anaruhusiwa kuandika (ili aweze
# kuwasha 2FA, kubadilisha nenosiri, kutoka n.k.). Badilisha kwa setting
# ADMIN_2FA_EXEMPT_PATH_PREFIXES.
DEFAULT_EXEMPT_PREFIXES = (
    "/api/auth/",
    "/api/2fa/", "/api/me/", "/api/profile/", "/api/logout/",
    "/api/password/", "/api/token/", "/api/sessions/",
)

CODE_REQUIRED = "admin_2fa_required"
CODE_LOGIN_REQUIRED = "admin_2fa_login_required"

MSG_REQUIRED = (
    "Akaunti za admin zinahitaji 2FA. Washa 2FA kwenye Wasifu wako "
    "kisha ujaribu tena."
)
MSG_LOGIN_REQUIRED = "Ingia tena kwa nenosiri na msimbo wa 2FA ili kuendelea."


def has_admin_2fa(user):
    """True kama mtumiaji ana TOTP iliyowashwa."""
    totp = getattr(user, "totp", None)
    return bool(totp and getattr(totp, "enabled", False))


def _token_has_mfa(request, token=_UNSET):
    if token is _UNSET:
        token = getattr(request, "auth", None)
    getter = getattr(token, "get", None)
    return bool(getter and getter(MFA_CLAIM))


def admin_2fa_failure(request, user=None, token=_UNSET):
    """
    Rudisha None kama sharti la 2FA limetimizwa (au limezimwa), vinginevyo
    (code, message). Haikagui kama mtumiaji ni staff — hilo ni la mwito.
    `user`/`token` ni za hiari (zinatumika wakati wa authentication, kabla
    `request.user`/`request.auth` hazijawekwa).
    """
    if not getattr(settings, "ADMIN_REQUIRE_2FA", True):
        return None
    user = user if user is not None else request.user
    if not has_admin_2fa(user):
        return CODE_REQUIRED, MSG_REQUIRED
    if getattr(settings, "ADMIN_2FA_ENFORCE_TOKEN_CLAIM", False) and not _token_has_mfa(request, token):
        return CODE_LOGIN_REQUIRED, MSG_LOGIN_REQUIRED
    return None


def require_admin_2fa(request):
    """Kwa views zinazokagua is_staff wenyewe: inatupa PermissionDenied ikikosa 2FA."""
    failure = admin_2fa_failure(request)
    if failure:
        code, message = failure
        raise PermissionDenied(detail=message, code=code)


def is_staff_with_2fa(request):
    user = getattr(request, "user", None)
    return bool(
        user and user.is_authenticated and user.is_staff
        and admin_2fa_failure(request) is None
    )


class IsAdminWith2FA(BasePermission):
    """Staff + 2FA iliyowashwa. Mbadala wa `IsAdminUser` kwa endpoints za admin."""

    # `message`/`code` zinawekwa kwenye instance TU 2FA inapokosekana, ili
    # kukataliwa kwa kawaida (si staff) kubaki na ujumbe wa kawaida wa DRF.
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_staff):
            return False
        failure = admin_2fa_failure(request)
        if failure:
            self.code, self.message = failure
            return False
        return True


# ------------------------------------------------------------------
# Ulinzi wa jumla wa kuandika (defense in depth)
# ------------------------------------------------------------------
def guard_staff_write(request, user, token=None):
    """
    Staff/superuser asiye na 2FA HAWEZI kuandika (POST/PUT/PATCH/DELETE)
    popote kwenye API, isipokuwa endpoints za auth. Hii inafunika views zote
    zenye ukaguzi wa mkono wa `is_staff` au permission class za kujitegemea,
    bila kuhariri kila faili. Kusoma (GET) hakuguswi kwa chaguo-msingi —
    kunalindwa na permission za kila view. Weka ADMIN_2FA_GUARD_READS = True
    ili staff asiye na 2FA afungiwe hata kusoma (zaidi ya endpoints za auth);
    washa baada ya admin wote kuwasha 2FA, kwa sababu pia inafunga kurasa za
    umma anapoingia akiwa na token (mf. anaposoma soko akiwa ameingia).
    """
    if request.method in SAFE_METHODS and not getattr(
        settings, "ADMIN_2FA_GUARD_READS", False
    ):
        return
    if not (user and getattr(user, "is_authenticated", False)
            and (user.is_staff or user.is_superuser)):
        return
    prefixes = tuple(
        getattr(settings, "ADMIN_2FA_EXEMPT_PATH_PREFIXES", DEFAULT_EXEMPT_PREFIXES)
    )
    if request.path.startswith(prefixes):
        return
    failure = admin_2fa_failure(request, user=user, token=token)
    if failure:
        code, message = failure
        raise PermissionDenied(detail=message, code=code)


class Admin2FAGuardMixin:
    """
    Changanya na authentication class yoyote ya DRF:

        class MyAuth(Admin2FAGuardMixin, JWTAuthentication): ...
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            guard_staff_write(request, user, token)
        return result
