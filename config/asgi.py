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

from config.ws_auth import JWTAuthMiddleware
from apps.deals.routing import websocket_urlpatterns


class OriginValidatorMiddleware(BaseMiddleware):
    """
    Validator yetu wenyewe inayoruhusu vyanzo maalum bila kutegemea
    ALLOWED_HOSTS. `AllowedHostsOriginValidator` ilikataa origin sahihi
    kwenye mazingira ya Docker Swarm + Traefik, kwa hiyo tunatumia hii.
    """

    ALLOWED_ORIGINS = [
        "https://www.sokomkononi.co.tz",
        "https://sokomkononi.co.tz",
    ]

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode(errors="replace")

        # Ikiwa hakuna Origin (baadhi ya clients za CLI), ruhusu.
        # Kwa browser, Origin ipo na lazima ilingane.
        if origin and origin not in self.ALLOWED_ORIGINS:
            await send({"type": "websocket.close", "code": 1008})
            return

        return await super().__call__(scope, receive, send)


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": OriginValidatorMiddleware(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})