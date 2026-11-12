"""
ASGI config — inashughulikia HTTP + WebSocket (Django Channels).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from config.ws_auth import JWTAuthMiddleware
from apps.deals.routing import websocket_urlpatterns


class DebugOriginValidator(BaseMiddleware):
    """Validator yetu wenyewe yenye debug prints."""

    async def __call__(self, scope, receive, send):
        # Pata Origin kutoka headers
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode(errors="replace")

        # Orodha ya vyanzo vinavyoruhusiwa
        allowed = [
            "https://www.sokomkononi.co.tz",
            "https://sokomkononi.co.tz",
        ]

        print(f"[ORIGIN VALIDATOR] origin={origin!r} allowed={allowed}")

        if origin not in allowed:
            print(f"[ORIGIN VALIDATOR] ❌ REJECTED: {origin!r} not in {allowed}")
            # Kataa muunganisho
            await send({"type": "websocket.close", "code": 403})
            return

        print(f"[ORIGIN VALIDATOR] ✅ ACCEPTED: {origin!r}")
        return await super().__call__(scope, receive, send)


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": DebugOriginValidator(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})