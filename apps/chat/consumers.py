import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.selectors.participant import is_user_participant


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Real-time layer for a single conversation.

    Responsibilities are intentionally narrow: track group membership
    and relay small ephemeral signals between connected clients.
    Persisting a message is NEVER handled here — that always goes
    through the HTTP POST endpoints (the session-authenticated web
    view or the JWT-authenticated mobile API), which call
    apps.chat.services.send_message. That service broadcasts the new
    message to this consumer's group itself, so this class doesn't
    need to know anything about how a message gets created — only
    how to relay events.

    Every message on the wire (both directions) uses the same small
    envelope: {"event": "<name>", "data": {...}}. Incoming events are
    dispatched via INCOMING_HANDLERS; outgoing events are sent by the
    broadcast_* Channels-layer handler methods (their name is what
    Channels dispatches group_send's "type" key to).
    """

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = f'conversation_{self.conversation_id}'
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        allowed = await database_sync_to_async(is_user_participant)(
            conversation_id=self.conversation_id, user=self.user
        )
        if not allowed:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # -----------------------------------------------------------
    # Client -> server: incoming event dispatch
    # -----------------------------------------------------------

    async def receive(self, text_data):
        """
        Parses {"event": ..., "data": ...} and dispatches to the
        matching handler in INCOMING_HANDLERS. Malformed JSON or an
        unknown event name is silently ignored rather than raising —
        a bad/future client message shouldn't be able to crash the
        connection.
        """
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        handler = self.INCOMING_HANDLERS.get(payload.get('event'))
        if handler is not None:
            await handler(self, payload.get('data') or {})

    async def _handle_typing(self, data):
        """
        Relays a "user is typing" signal to everyone in the group,
        including the sender's own connection — Channels groups have
        no built-in "everyone except me" send, so the client is
        responsible for ignoring events where user_id is its own.
        """
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_typing',
                'user_id': str(self.user.id),
                'username': self.user.username,
            },
        )

    async def _handle_seen(self, data):
        """Placeholder for read receipts — implemented in a later phase."""
        pass

    INCOMING_HANDLERS = {
        'typing': _handle_typing,
        'seen': _handle_seen,
    }

    # -----------------------------------------------------------
    # Server -> client: Channels group event handlers
    # -----------------------------------------------------------

    async def broadcast_new_message(self, event):
        """Triggered by services.realtime.broadcast_new_message for every new message, from any entry point."""
        await self.send(text_data=json.dumps({
            'event': 'message.new',
            'data': {
                'id': event['message_id'],
                'conversation_id': event['conversation_id'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'content': event['content'],
                'created_at': event['created_at'],
            },
        }))

    async def broadcast_typing(self, event):
        await self.send(text_data=json.dumps({
            'event': 'typing',
            'data': {'user_id': event['user_id'], 'username': event['username']},
        }))