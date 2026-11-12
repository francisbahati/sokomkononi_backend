"""
WebSocket JWT authentication middleware.

Frontend inatuma token kama `?token=<jwt>` kwenye URL ya WebSocket
(browser haiwezi kuweka Authorization header kwenye WebSocket API).

Middleware hii inasoma token, inamthibitisha, na kumweka kwenye
`scope["user"]`.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user_from_token(token_str):
    """Decode JWT na rudisha User (au AnonymousUser)."""
    try:
        token = AccessToken(token_str)
        user_id = token.get("user_id")
        if not user_id:
            return AnonymousUser()

        User = get_user_model()
        user = User.objects.filter(id=user_id, is_active=True).first()
        return user or AnonymousUser()
    except (InvalidToken, TokenError, Exception):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Inasoma JWT kutoka:
      1. Query string: `?token=<jwt>`   (frontend inatumia hii)
      2. Header: `Authorization: Bearer <jwt>` (fallback)
    """

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        query_string = scope.get("query_string", b"").decode(errors="replace")

        # ── Token kutoka query string ──
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])
        token = token_list[0] if token_list else None

        # ── Fallback: Authorization header ──
        if not token:
            auth_header = headers.get(b"authorization", b"").decode(errors="replace")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)