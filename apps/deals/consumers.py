"""
DealRoomConsumer — WebSocket consumer kwa deal rooms.

Vipengele:
  ✅ accept() inaitwa KABLA ya close() ili code ya kufunga ifike kwa mteja.
  ✅ Heartbeat ya kila sekunde 30 ili Cloudflare isikate connection
     (Cloudflare ina timeout ya sekunde 100 kwa WebSocket idle).
  ✅ Typing indicator — inasambaza {"type": "typing"} kwa wanachama wengine.
  ✅ Broadcast ya ujumbe mpya, ofa, na deal updates kupitia group_send.
"""
import asyncio

from django.db import models

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


class DealRoomConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")
        self.room_id = self.scope["url_route"]["kwargs"].get("room_id")
        self.group_name = f"deal_room_{self.room_id}"
        self._heartbeat_task = None

        # ⚠️ MUHIMU: accept() kwanza ili code ya kufunga ifike kwa mteja.
        # Bila hii, Daphne hurudisha 403 na kivinjari kinaona 1006.
        await self.accept()

        # Auth
        if not self.user or isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        # Participant check
        is_participant = await self._is_participant()
        if not is_participant:
            await self.close(code=4003)
            return

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Tuma "connected" kwa mteja
        await self.send_json({
            "type": "connected",
            "room_id": self.room_id,
            "user_id": self.user.id,
        })

        # ✅ Heartbeat: kila sekunde 30, tuma "ping" kwa mteja
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, code):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    async def _heartbeat_loop(self):
        """Tuma ping kila sekunde 30 (Cloudflare ina timeout ya 100s)."""
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await self.send_json({"type": "ping"})
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

        if msg_type == "pong":
            return

        if msg_type == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "typing.event",
                    "user_id": self.user.id,
                    "user_name": getattr(self.user, "full_name", None)
                    or self.user.email,
                    "is_typing": bool(content.get("is_typing")),
                },
            )
            return

        # Ujumbe wa kawaida (message) unaendelea kupitia HTTP POST.
        # Broadcast ya ujumbe mpya inafanywa na views/services kupitia
        # `broadcast_deal_event()` (ona apps/deals/services/ws_broadcast.py).

    # ── Group event handlers ──

    async def typing_event(self, event):
        # Usimtumie mtumiaji mwenyewe typing yake
        if event["user_id"] == self.user.id:
            return
        await self.send_json({
            "type": "typing",
            "user_id": event["user_id"],
            "user_name": event["user_name"],
            "is_typing": event["is_typing"],
        })

    async def deal_event(self, event):
        """Handler ya jumla kwa broadcast ya ujumbe/ofa/deal update."""
        # Tuma payload yote kwa mteja
        await self.send_json({
            "type": event.get("event_type", "message"),
            "room_id": self.room_id,
            "payload": event.get("payload", {}),
        })

    @database_sync_to_async
    def _is_participant(self):
        from .models import DealRoom
        return DealRoom.objects.filter(pk=self.room_id).filter(
            models.Q(buyer_id=self.user.id) | models.Q(seller_id=self.user.id)
        ).exists()