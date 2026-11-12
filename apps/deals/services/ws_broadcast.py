"""
Helper ya kutuma broadcast ya matukio ya deal room kupitia Django Channels.

Inatumika na views/services baada ya:
  - create_message
  - create_offer / accept_offer / decline_offer
  - deal status changes
  - reservation events

Inatuma kwa group `deal_room_<room_id>` ambalo DealRoomConsumer amejiunga nalo.
"""
import logging
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def _room_group_name(room_id):
    return f"deal_room_{room_id}"


def _json_safe(value):
    """Badilisha Decimal/date kuwa JSON-serializable."""
    if isinstance(value, Decimal):
        return str(value)
    return value


def broadcast_deal_event(room_id, event_type, payload):
    """
    Tuma tukio la deal room kwa wanachama wote wa chumba.

    :param room_id: ID ya DealRoom
    :param event_type: "message" | "offer" | "offer_update" | "deal_update"
    :param payload: dict yenye data ya tukio (JSON-serializable)
    """
    if room_id is None:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("broadcast_deal_event: hakuna channel layer")
        return

    group = _room_group_name(room_id)
    try:
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "deal_event",
                "event_type": event_type,
                "payload": payload,
            },
        )
    except Exception:
        logger.exception("broadcast_deal_event imeshindwa (room=%s)", room_id)


def broadcast_new_message(room_id, message_data):
    """Broadcast ya ujumbe mpya (text/image)."""
    broadcast_deal_event(room_id, "message", message_data)


def broadcast_new_offer(room_id, offer_data):
    """Broadcast ya ofa mpya."""
    broadcast_deal_event(room_id, "offer", offer_data)


def broadcast_offer_update(room_id, offer_data):
    """Broadcast ya ofa iliyokubaliwa/kukataliwa."""
    broadcast_deal_event(room_id, "offer_update", offer_data)


def broadcast_deal_update(room_id, deal_data):
    """Broadcast ya mabadiliko ya deal (status, reservation, n.k.)."""
    broadcast_deal_event(room_id, "deal_update", deal_data)