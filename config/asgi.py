"""
ASGI config — inashughulikia HTTP + WebSocket (Django Channels).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# ⚠️ LAZIMA: get_asgi_application() iitwe KABLA ya imports zozote za apps.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from config.ws_auth import JWTAuthMiddleware
from apps.deals.routing import websocket_urlpatterns


class OriginValidatorMiddleware(BaseMiddleware):
    """
    Validator yetu wenyewe yenye debug prints.
    Inaruhusu vyanzo maalum bila kutegemea ALLOWED_HOSTS.
    """

    ALLOWED_ORIGINS = [
        "https://www.sokomkononi.co.tz",
        "https://sokomkononi.co.tz",
    ]

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode(errors="replace")
        host = headers.get(b"host", b"").decode(errors="replace")

        print(
            f"[ORIGIN VALIDATOR] origin={origin!r} host={host!r} "
            f"allowed={self.ALLOWED_ORIGINS}"
        )

        # Ikiwa hakuna Origin (baadhi ya clients za CLI), ruhusu.
        # Kwa browser, Origin ipo na lazima ilingane.
        if origin and origin not in self.ALLOWED_ORIGINS:
            print(f"[ORIGIN VALIDATOR] ❌ REJECTED: {origin!r}")
            # Tuma close KABLA ya accept — Daphne itarudisha 403.
            # Hii ni sawa kwa origin isiyo halali.
            await send({"type": "websocket.close", "code": 1008})
            return

        print(f"[ORIGIN VALIDATOR] ✅ ACCEPTED: {origin!r}")
        return await super().__call__(scope, receive, send)


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": OriginValidatorMiddleware(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})