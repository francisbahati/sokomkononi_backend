"""
WebSocket URL routing ya apps.deals.
"""
from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    # /ws/deal/<room_id>/?token=<jwt>
    re_path(
        r"^ws/deal/(?P<room_id>\d+)/$",
        consumers.DealRoomConsumer.as_asgi(),
    ),
]