"""
Flexible JWT authentication.

Token sources (in priority order):
  1. Authorization: Bearer <token>       — no CSRF required
  2. Header: X-Access-Token: <token>     — no CSRF required
  3. Cookie: access_token=<token>        — CSRF enforced

Important behaviour:
  If the token comes from a cookie AND the CSRF check fails, we
  return None (treat the request as unauthenticated) instead of
  raising. This lets public endpoints — especially /api/auth/login/
  during a re-login while a stale cookie is still present — work
  normally, while every IsAuthenticated view still rejects the
  request with 401.
"""
import logging

from django.middleware.csrf import CsrfViewMiddleware

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


logger = logging.getLogger(__name__)


class _CSRFCheck(CsrfViewMiddleware):
    """Return the rejection reason instead of rendering an HTML page."""

    def _reject(self, request, reason):
        return reason


class FlexibleJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        # 1) Authorization header — handled by the parent class.
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

        # Strictly access tokens only.
        if not isinstance(validated, AccessToken):
            return None
        if validated.get("purpose"):
            return None

        # A cookie-sourced token must also pass CSRF verification.
        # On failure we log and return None — the request continues
        # as anonymous. Any view that requires authentication will
        # reject it with a normal 401.
        if from_cookie and not self._csrf_ok(request):
            logger.warning(
                "FlexibleJWT: cookie auth rejected by CSRF check (%s %s)",
                request.method, request.path,
            )
            return None

        return (self.get_user(validated), validated)

    # --------------------------------------------------------------
    # CSRF helpers
    # --------------------------------------------------------------
    def _csrf_ok(self, request) -> bool:
        """Return True if the CSRF check passes for this request."""
        # Safe methods are always fine.
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return True

        check = _CSRFCheck(lambda r: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        return not reason
