"""
Flexible JWT authentication.

Reads the access token from (in priority order):
  1. Authorization: Bearer <token>          (no CSRF required)
  2. Cookie:         access_token=<token>   (CSRF enforced)
  3. Header:         X-Access-Token: <token>(no CSRF required)
"""
from django.middleware.csrf import CsrfViewMiddleware

from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class _CSRFCheck(CsrfViewMiddleware):
    """Raises 403 rather than rendering the default 403 HTML page."""

    def _reject(self, request, reason):
        return reason


class FlexibleJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 1) Authorization header — handled by parent.
        result = super().authenticate(request)
        if result is not None:
            return result

        # 2) Cookie or X-Access-Token header.
        raw = None
        from_cookie = False

        cookie_token = request.COOKIES.get("access_token")
        header_token = request.META.get("HTTP_X_ACCESS_TOKEN")

        if cookie_token:
            raw = cookie_token
            from_cookie = True
        elif header_token:
            raw = header_token

        if not raw:
            return None

        try:
            validated = self.get_validated_token(raw)
        except (InvalidToken, TokenError):
            return None

        # Only accept true access tokens.
        if validated.get("token_type") != "access":
            return None
        if validated.get("purpose"):
            return None

        # A cookie-sourced token must pass CSRF verification.
        if from_cookie:
            self._enforce_csrf(request)

        return (self.get_user(validated), validated)

    def _enforce_csrf(self, request):
        check = _CSRFCheck(lambda r: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise PermissionDenied(f"CSRF Failed: {reason}")
