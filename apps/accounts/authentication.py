"""
Flexible JWT authentication.

Reads the access token from any of:
  1. Authorization: Bearer <token>
  2. Cookie:         access_token=<token>
  3. Query string:   ?token=<token>
  4. Header:         X-Access-Token: <token>

Security is unchanged — the token must still be a valid, unexpired
JWT and the user must still pass every permission check.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class FlexibleJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            return result

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
