import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.selectors.participant import is_user_participant
from apps.chat.services import send_message


class ChatConsumer(AsyncWebsocketConsumer):
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

    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data.get('content', '').strip()

        if not content:
            return

        message = await database_sync_to_async(send_message)(
            conversation_id=self.conversation_id, sender=self.user, content=content
        )

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'message_id': str(message.id),
                'sender_id': str(self.user.id),
                'sender_username': self.user.username,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message_id': event['message_id'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'content': event['content'],
            'created_at': event['created_at'],
        }))