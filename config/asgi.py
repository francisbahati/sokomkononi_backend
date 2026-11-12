"""
ASGI config — inashughulikia HTTP + WebSocket (Django Channels).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# ⚠️ LAZIMA: get_asgi_application() iitwe KABLA ya imports zozote za apps.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator

from config.ws_auth import JWTAuthMiddleware
from apps.deals.routing import websocket_urlpatterns


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": OriginValidator(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
        ["https://www.sokomkononi.co.tz", "https://sokomkononi.co.tz"],
    ),
})