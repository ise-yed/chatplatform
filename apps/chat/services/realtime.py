from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_new_message(*, message):
    """
    Notifies every WebSocket consumer subscribed to this message's
    conversation group that a new message was created — regardless of
    whether the request came from the web (session auth) or mobile
    (JWT) entry point. Called from apps.chat.services.message.send_message
    right after the message is persisted, so broadcasting is never the
    caller's responsibility to remember.

    All fields the client needs to render the message are included
    directly in the event payload, so no consumer needs a database
    query to relay it (message.sender is already the in-memory User
    instance passed into Message.objects.create, not a lazy reference).
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'conversation_{message.conversation_id}',
        {
            'type': 'broadcast_new_message',
            'message_id': str(message.id),
            'conversation_id': str(message.conversation_id),
            'sender_id': str(message.sender_id),
            'sender_username': message.sender.username,
            'content': message.content,
            'created_at': message.created_at.isoformat(),
        },
    )