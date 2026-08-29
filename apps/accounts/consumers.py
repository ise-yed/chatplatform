import asyncio
import json

from channels.generic.websocket import AsyncWebsocketConsumer

from apps.accounts.services.presence import (
    HEARTBEAT_INTERVAL_SECONDS,
    refresh_heartbeat,
    register_connection,
    unregister_connection,
)
from apps.accounts.services.realtime import PRESENCE_GROUP
from apps.common.constants import (
    BROADCAST_PRESENCE_UPDATE,
    SESSION_REVOKED,
    device_session_group,
)


class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.session_id = self.scope.get('session_id')

        await self.channel_layer.group_add(PRESENCE_GROUP, self.channel_name)

        # See apps.chat.consumers.ChatConsumer for why this group join
        # exists: it's what lets broadcast_session_revoked() force-close
        # this connection the instant its DeviceSession is revoked.
        if self.session_id:
            self.session_group_name = device_session_group(self.session_id)
            await self.channel_layer.group_add(self.session_group_name, self.channel_name)

        await self.accept()
        await register_connection(user_id=self.user.id, channel_name=self.channel_name)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, close_code):
        if hasattr(self, '_heartbeat_task'):
            self._heartbeat_task.cancel()

        if not hasattr(self, 'user') or self.user.is_anonymous:
            return

        await self.channel_layer.group_discard(PRESENCE_GROUP, self.channel_name)

        if hasattr(self, 'session_group_name'):
            await self.channel_layer.group_discard(self.session_group_name, self.channel_name)

        await unregister_connection(user_id=self.user.id, channel_name=self.channel_name)

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                await refresh_heartbeat(channel_name=self.channel_name)
        except asyncio.CancelledError:
            pass



    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            'event': BROADCAST_PRESENCE_UPDATE,
            'data': {
                'user_id': event['user_id'],
                'is_online': event['is_online'],
                'last_seen': event.get('last_seen'),
            },
        }))

    async def broadcast_session_revoked(self, event):
        """See apps.chat.consumers.ChatConsumer.broadcast_session_revoked — same reason, same effect, just on the presence socket."""
        await self.send(text_data=json.dumps({'event': SESSION_REVOKED, 'data': {}}))
        await self.close(code=4008)