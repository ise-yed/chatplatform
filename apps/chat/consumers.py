import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.selectors.participant import is_user_participant
from apps.chat.services.participant import mark_conversation_as_read
from apps.common.constants import (
    BROADCAST_PRESENCE,
    BROADCAST_TYPING,
    NEW_MESSAGE,
    READ_RECEIPT,
    SESSION_REVOKED,
    TYPING,
    device_session_group,
)


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
        self.session_id = self.scope.get('session_id')

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

        # Only JWT-authenticated connections carry a session_id (see
        # apps.chat.middleware.get_user_and_session_from_token). Joining
        # this group is what lets broadcast_session_revoked() reach and
        # force-close this exact connection the moment its DeviceSession
        # gets revoked, instead of leaving it open until the access
        # token happens to expire on its own.
        if self.session_id:
            self.session_group_name = device_session_group(self.session_id)
            await self.channel_layer.group_add(self.session_group_name, self.channel_name)

        await self.accept()
        

        await database_sync_to_async(mark_conversation_as_read)(
            conversation_id=self.conversation_id, user=self.user
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

        if hasattr(self, 'session_group_name'):
            await self.channel_layer.group_discard(
                self.session_group_name,
                self.channel_name,
            )

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

    async def _handle_typing_start(self, data):
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': BROADCAST_TYPING,
                'user_id': str(self.user.id),
                'username': self.user.username,
                'is_typing': True,
            },
        )


    async def _handle_typing_stop(self, data):
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': BROADCAST_TYPING,
                'user_id': str(self.user.id),
                'username': self.user.username,
                'is_typing': False,
            },
        )


    async def _handle_seen(self, data):
        """
        Marks the conversation as read up to the given message (or the
        latest message if none is given). Sent by the client when a
        new message arrives while the conversation window is visible.
        """
        await database_sync_to_async(mark_conversation_as_read)(
            conversation_id=self.conversation_id, user=self.user, message_id=data.get('message_id')
        )

    INCOMING_HANDLERS = {
    'typing.start': _handle_typing_start,
    'typing.stop': _handle_typing_stop,
        'seen': _handle_seen,
    }

    # -----------------------------------------------------------
    # Server -> client: Channels group event handlers
    # -----------------------------------------------------------

    async def broadcast_new_message(self, event):
        """Triggered by services.realtime.broadcast_new_message for every new message, from any entry point."""
        await self.send(text_data=json.dumps({
            'event': NEW_MESSAGE,
            'data': {
                'id': event['message_id'],
                'conversation_id': event['conversation_id'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'content': event['content'],
                'created_at': event['created_at'],
                'type': event['message_type'],
                'attachment_url': event['attachment'],
                'file_name': event['file_name'],
                'file_size': event['file_size'],

            },
        }))

    async def broadcast_typing(self, event):
        await self.send(text_data=json.dumps({
            'event': TYPING,
            'data': {'user_id': event['user_id'], 'username': event['username'], 'is_typing': event['is_typing']},
        }))
        
    # async def broadcast_presence(self, event):
    #     await self.send(text_data=json.dumps({
    #         'event': BROADCAST_PRESENCE,
    #         'data': {
    #             'user_id': event['user_id'],
    #             'username': event['username'],
    #             'is_online': event['is_online'],
    #         },
    #     }))
    
    async def broadcast_read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'event': READ_RECEIPT,
            'data': {'user_id': event['user_id'], 'last_read_message_id': event['last_read_message_id']},
        }))

    async def broadcast_session_revoked(self, event):
        """
        Triggered by apps.accounts.services.realtime.broadcast_session_revoked
        right after a DeviceSession is revoked (single-session revoke or
        "log out everywhere"). Tells the client why the socket is closing
        so it can show a proper message instead of silently retrying,
        then force-closes the connection — this device stops receiving
        chat events immediately rather than waiting for its access token
        to expire on its own.
        """
        await self.send(text_data=json.dumps({'event': SESSION_REVOKED, 'data': {}}))
        await self.close(code=4008)