"""
Helper ya kutuma broadcast ya matukio ya deal room kupitia Django Channels,
pamoja na push notifications kwa mtumiaji ambaye hayupo kwenye chumba.
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
    Tuma tukio la deal room kwa wanachama wote wa chumba (WebSocket).
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


def _send_push_to_counterparty(deal_room_id, sender_id, title, body, url):
    """
    Tuma push notification kwa upande wa pili (si yule aliyetuma).
    Inaitwa ndani ya `transaction.on_commit`.
    """
    try:
        from apps.deals.models import DealRoom
        from apps.push.send import send_push_to_user

        deal_room = (
            DealRoom.objects
            .select_related("buyer", "seller")
            .only("buyer_id", "seller_id", "buyer__id", "seller__id")
            .get(pk=deal_room_id)
        )

        # Chagua mpokeaji: yule ambaye SI sender
        if deal_room.buyer_id == sender_id:
            recipient = deal_room.seller
        else:
            recipient = deal_room.buyer

        if recipient is None:
            return

        result = send_push_to_user(
            user=recipient,
            title=title,
            body=body,
            url=url,
            tag=f"deal-{deal_room_id}",
        )
        if result.get("failed") or result.get("error"):
            logger.warning(
                "push notification kwa deal %s: %s", deal_room_id, result,
            )
    except Exception:
        logger.exception(
            "push notification imeshindwa (room=%s)", deal_room_id,
        )


def notify_deal_participants(
    *,
    room_id,
    event_type,
    payload,
    sender_id,
    push_title,
    push_body,
    push_url,
):
    """
    Tuma broadcast (WebSocket) kwa wanachama wote wa chumba + push
    notification kwa upande wa pili (ambaye hayupo kwenye chumba).
    """
    # 1) WebSocket broadcast (wote walioko kwenye chumba)
    broadcast_deal_event(room_id, event_type, payload)

    # 2) Push notification kwa mpokeaji (baada ya commit)
    from django.db import transaction as db_transaction
    db_transaction.on_commit(
        lambda: _send_push_to_counterparty(
            deal_room_id=room_id,
            sender_id=sender_id,
            title=push_title,
            body=push_body,
            url=push_url,
        )
    )


def broadcast_new_message(room_id, message_data):
    """Broadcast ya ujumbe mpya (text/image) — pamoja na push."""
    sender_id = message_data.get("sender_id")
    sender_name = message_data.get("sender_name") or "Mtu"
    text = message_data.get("text") or (
        "📎 Picha" if message_data.get("attachment_url") else ""
    )

    notify_deal_participants(
        room_id=room_id,
        event_type="message",
        payload=message_data,
        sender_id=sender_id,
        push_title=f"Ujumbe mpya kutoka {sender_name}",
        push_body=text[:120],
        push_url=f"/dashboard/deals?deal={room_id}",
    )


def broadcast_new_offer(room_id, offer_data):
    """Broadcast ya ofa mpya — pamoja na push."""
    sender_id = offer_data.get("sender_id")
    amount = offer_data.get("offer_amount") or ""

    notify_deal_participants(
        room_id=room_id,
        event_type="offer",
        payload=offer_data,
        sender_id=sender_id,
        push_title="Ofa mpya",
        push_body=f"Ofa ya TZS {amount} imepokelewa.",
        push_url=f"/dashboard/deals?deal={room_id}",
    )


def broadcast_offer_update(room_id, offer_data):
    """Broadcast ya ofa iliyokubaliwa/kukataliwa."""
    broadcast_deal_event(room_id, "offer_update", offer_data)


def broadcast_deal_update(room_id, deal_data):
    """Broadcast ya mabadiliko ya deal (status, reservation, n.k.)."""
    broadcast_deal_event(room_id, "deal_update", deal_data)