# apps/core/tests/test_admin_2fa.py
from types import SimpleNamespace

from django.conf import settings as dj_settings
from django.test import SimpleTestCase, override_settings
from django.utils.module_loading import import_string
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.core.admin_2fa import Admin2FAGuardMixin, IsAdminWith2FA, has_admin_2fa
from apps.core.permissions import IsAdminOrReadOnly, IsAdminUser, IsSuperUser


def _user(*, staff=True, superuser=False, auth=True, totp=None):
    return SimpleNamespace(
        pk=1, id=1,
        is_authenticated=auth, is_staff=staff, is_superuser=superuser, totp=totp,
    )


ON = SimpleNamespace(enabled=True)
OFF = SimpleNamespace(enabled=False)
factory = APIRequestFactory()


def _call(perm_class, user, *, method="post", token=None):
    class V(APIView):
        permission_classes = [perm_class]
        throttle_classes = []  # mradi unaweza kuwa na throttle; hapa hazihitajiki

        def post(self, request):
            return Response({"ok": True})

        get = post

    req = getattr(factory, method)("/x/")
    if user is not None:
        force_authenticate(req, user=user, token=token)
    resp = V.as_view()(req)
    resp.render()
    return resp


class PermissionUnitTests(SimpleTestCase):
    def test_anonymous_denied(self):
        self.assertFalse(IsAdminWith2FA().has_permission(
            SimpleNamespace(user=_user(auth=False), auth=None), None))

    def test_has_admin_2fa_handles_missing_relation(self):
        class NoTotp:
            @property
            def totp(self):
                raise AttributeError("RelatedObjectDoesNotExist")
        self.assertFalse(has_admin_2fa(NoTotp()))


class AdminEndpointTests(SimpleTestCase):
    """Kupitia APIView halisi + exception handler ya mradi."""

    def test_staff_without_2fa_gets_clear_403(self):
        r = _call(IsAdminUser, _user(totp=None))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "ADMIN_2FA_REQUIRED")
        self.assertIn("2FA", r.data["error"]["message"])

    def test_staff_with_2fa_disabled_denied(self):
        self.assertEqual(_call(IsAdminUser, _user(totp=OFF)).status_code, 403)

    def test_staff_with_2fa_allowed(self):
        self.assertEqual(_call(IsAdminUser, _user(totp=ON)).status_code, 200)

    def test_non_staff_gets_plain_permission_denied(self):
        r = _call(IsAdminUser, _user(staff=False, totp=ON))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "PERMISSION_DENIED")

    def test_anonymous_gets_401_or_403(self):
        r = _call(IsAdminUser, None)
        self.assertIn(r.status_code, (401, 403))

    @override_settings(ADMIN_REQUIRE_2FA=False)
    def test_switch_off(self):
        self.assertEqual(_call(IsAdminUser, _user(totp=None)).status_code, 200)
        self.assertEqual(_call(IsAdminUser, _user(staff=False)).status_code, 403)

    @override_settings(ADMIN_2FA_ENFORCE_TOKEN_CLAIM=True)
    def test_token_claim_enforced(self):
        u = _user(totp=ON)
        r = _call(IsAdminUser, u, token={"user_id": 1})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "ADMIN_2FA_LOGIN_REQUIRED")
        self.assertEqual(_call(IsAdminUser, u, token=None).status_code, 403)
        self.assertEqual(_call(IsAdminUser, u, token={"mfa": True}).status_code, 200)

    def test_claim_not_checked_by_default(self):
        self.assertEqual(
            _call(IsAdminUser, _user(totp=ON), token={"user_id": 1}).status_code, 200)

    # ---- IsSuperUser
    def test_superuser_needs_2fa(self):
        self.assertEqual(
            _call(IsSuperUser, _user(superuser=True, totp=None)).status_code, 403)
        self.assertEqual(
            _call(IsSuperUser, _user(superuser=True, totp=ON)).status_code, 200)
        self.assertEqual(
            _call(IsSuperUser, _user(superuser=False, totp=ON)).status_code, 403)

    # ---- IsAdminOrReadOnly
    def test_read_only_stays_open(self):
        self.assertEqual(
            _call(IsAdminOrReadOnly, _user(staff=False), method="get").status_code, 200)

    def test_write_needs_staff_with_2fa(self):
        self.assertEqual(
            _call(IsAdminOrReadOnly, _user(totp=None), method="post").status_code, 403)
        self.assertEqual(
            _call(IsAdminOrReadOnly, _user(totp=ON), method="post").status_code, 200)
        self.assertEqual(
            _call(IsAdminOrReadOnly, _user(staff=False, totp=ON), method="post").status_code, 403)


# ------------------------------------------------------------------
# Ulinzi wa jumla wa kuandika (authentication-level guard)
# ------------------------------------------------------------------
_CURRENT = {"user": None, "token": None}


class _BaseAuth:
    def authenticate(self, request):
        return (_CURRENT["user"], _CURRENT["token"])


class _GuardedAuth(Admin2FAGuardMixin, _BaseAuth):
    pass


def _guarded(user, *, method="post", path="/api/listings/", token=None):
    _CURRENT["user"], _CURRENT["token"] = user, token

    class V(APIView):
        authentication_classes = [_GuardedAuth]
        permission_classes = [AllowAny]
        throttle_classes = []

        def post(self, request):
            return Response({"ok": True})

        get = patch = delete = put = post

    req = getattr(factory, method)(path)
    resp = V.as_view()(req)
    resp.render()
    return resp


class StaffWriteGuardTests(SimpleTestCase):
    def test_staff_without_2fa_cannot_write_anywhere(self):
        r = _guarded(_user(totp=None))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "ADMIN_2FA_REQUIRED")
        for m in ("patch", "put", "delete"):
            self.assertEqual(_guarded(_user(totp=None), method=m).status_code, 403)

    def test_superuser_without_2fa_cannot_write(self):
        r = _guarded(_user(staff=False, superuser=True, totp=None))
        self.assertEqual(r.status_code, 403)

    def test_staff_without_2fa_can_still_read(self):
        self.assertEqual(_guarded(_user(totp=None), method="get").status_code, 200)

    def test_auth_endpoints_exempt_so_2fa_can_be_enabled(self):
        for p in ("/api/auth/2fa/setup/", "/api/auth/2fa/verify/",
                  "/api/auth/password/change/", "/api/auth/logout/"):
            self.assertEqual(_guarded(_user(totp=None), path=p).status_code, 200, p)

    def test_staff_with_2fa_can_write(self):
        self.assertEqual(_guarded(_user(totp=ON)).status_code, 200)

    def test_regular_user_unaffected(self):
        self.assertEqual(_guarded(_user(staff=False, totp=None)).status_code, 200)

    @override_settings(ADMIN_REQUIRE_2FA=False)
    def test_switch_off(self):
        self.assertEqual(_guarded(_user(totp=None)).status_code, 200)

    @override_settings(ADMIN_2FA_ENFORCE_TOKEN_CLAIM=True)
    def test_claim_enforced_on_writes(self):
        u = _user(totp=ON)
        r = _guarded(u, token={"user_id": 1})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "ADMIN_2FA_LOGIN_REQUIRED")
        self.assertEqual(_guarded(u, token={"mfa": True}).status_code, 200)

    @override_settings(ADMIN_2FA_EXEMPT_PATH_PREFIXES=("/api/special/",))
    def test_custom_exempt_prefixes(self):
        self.assertEqual(_guarded(_user(totp=None), path="/api/special/x/").status_code, 200)
        self.assertEqual(_guarded(_user(totp=None), path="/api/auth/2fa/setup/").status_code, 403)

    # ---- ADMIN_2FA_GUARD_READS: funga hata kusoma (hiari)
    @override_settings(ADMIN_2FA_GUARD_READS=True)
    def test_guard_reads_blocks_staff_without_2fa(self):
        r = _guarded(_user(totp=None), method="get")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "ADMIN_2FA_REQUIRED")

    @override_settings(ADMIN_2FA_GUARD_READS=True)
    def test_guard_reads_still_exempts_auth_and_allows_2fa_users(self):
        self.assertEqual(
            _guarded(_user(totp=None), method="get", path="/api/auth/me/").status_code, 200)
        self.assertEqual(_guarded(_user(totp=ON), method="get").status_code, 200)
        self.assertEqual(
            _guarded(_user(staff=False, totp=None), method="get").status_code, 200)


# ------------------------------------------------------------------
# Wiring ya settings — hii ndiyo inakamata kosa la "guard iko ya pili"
# ------------------------------------------------------------------
class SettingsWiringTests(SimpleTestCase):
    def _classes(self):
        classes = dj_settings.REST_FRAMEWORK.get("DEFAULT_AUTHENTICATION_CLASSES") or ()
        if not classes:
            self.skipTest("DEFAULT_AUTHENTICATION_CLASSES haijasanidiwa kwenye mazingira haya")
        return [import_string(c) for c in classes]

    def test_first_authentication_class_enforces_2fa_guard(self):
        """DRF hutumia authenticator ya kwanza inayofanikiwa; guard lazima iwe ndani yake."""
        first = self._classes()[0]
        self.assertTrue(
            issubclass(first, Admin2FAGuardMixin),
            f"{first.__module__}.{first.__name__} haina Admin2FAGuardMixin — "
            "ulinzi wa 2FA haufanyi kazi.",
        )
