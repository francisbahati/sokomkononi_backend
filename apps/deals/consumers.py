"""
DealRoomConsumer — skeleton (Awamu 1) + heartbeat.

Marekebisho:
  ✅ accept() inaitwa KABLA ya close() ili code ya kufunga ifike kwa mteja.
  ✅ Heartbeat ya kila sekunde 30 ili Cloudflare isikate connection
     (Cloudflare ina timeout ya sekunde 100 kwa WebSocket idle).
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
        elif msg_type == "pong":
            pass

    @database_sync_to_async
    def _is_participant(self):
        from .models import DealRoom
        return DealRoom.objects.filter(pk=self.room_id).filter(
            models.Q(buyer_id=self.user.id) | models.Q(seller_id=self.user.id)
        ).exists()