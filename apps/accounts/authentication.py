"""
Flexible JWT authentication.

Accepts the JWT from any of:
  1. Authorization: Bearer <token>       (standard — works today)
  2. Cookie: access_token=<token>        (browser fallback)
  3. Query string: ?token=<token>        (last-resort fallback)
  4. Header: X-Access-Token: <token>     (custom)

This lets endpoints that the frontend forgets to attach the
Authorization header to still work, without weakening any
permission checks — the token still has to be valid and the
user still has to be staff.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class FlexibleJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Try the standard Authorization: Bearer path first.
        result = super().authenticate(request)
        if result is not None:
            return result

        # Fallbacks, in order of preference.
        raw = (
            request.COOKIES.get("access_token")
            or request.query_params.get("token")
            or request.META.get("HTTP_X_ACCESS_TOKEN")
        )
        if not raw:
            return None

        try:
            validated = self.get_validated_token(raw)
        except (InvalidToken, TokenError):
            return None

        return (self.get_user(validated), validated)
