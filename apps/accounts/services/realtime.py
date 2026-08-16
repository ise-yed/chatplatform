from channels.layers import get_channel_layer

from apps.common.constants import PRESENCE_GROUP

async def broadcast_presence_change(*, user_id, is_online, last_seen=None):
    """
    Notifies every connected PresenceConsumer that a user's online
    status changed — used to update online dots and "last seen" text
    on the conversation list and chat header in real time.

    Unlike apps.chat.services.realtime (which wraps group_send with
    async_to_sync, since it's called from fully synchronous service
    functions), this one is called directly from an async context
    (PresenceConsumer itself), so it awaits group_send natively.
    Wrapping it in async_to_sync here would raise a RuntimeError —
    you can't nest AsyncToSync inside an already-running event loop
    on the same thread.
    """
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        PRESENCE_GROUP,
        {
            'type': 'presence_update',
            'user_id': str(user_id),
            'is_online': is_online,
            'last_seen': last_seen.isoformat() if last_seen else None,
        },
    )