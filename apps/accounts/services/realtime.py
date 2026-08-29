from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.common.constants import (
    BROADCAST_PRESENCE_UPDATE,
    BROADCAST_SESSION_REVOKED,
    PRESENCE_GROUP,
    device_session_group,
)


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
            # BUG FIX: this was the quoted literal 'BROADCAST_PRESENCE_UPDATE'
            # (the constant's name) instead of its value. Channels dispatches
            # group_send by treating "type" as a method name (dots become
            # underscores), so the old string never matched PresenceConsumer's
            # presence_update method — every presence broadcast raised inside
            # whichever consumer received it. Must be the constant's *value*.
            'type': BROADCAST_PRESENCE_UPDATE,
            'user_id': str(user_id),
            'is_online': is_online,
            'last_seen': last_seen.isoformat() if last_seen else None,
        },
    )


def broadcast_session_revoked(*, session_id):
    """
    Force-disconnects every WebSocket connection (chat + presence) tied
    to one DeviceSession. Called from
    apps.accounts.services.authentication.revoke_device_session right
    after a session is revoked, so "remove this device" / "log out
    everywhere" takes effect immediately instead of waiting for that
    device's access token to expire naturally (up to
    SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']).

    Sync wrapper (async_to_sync) because this is called from
    apps.accounts.services.authentication, which runs in a fully
    synchronous request/service context — same reasoning as
    apps.chat.services.realtime.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        device_session_group(session_id),
        {'type': BROADCAST_SESSION_REVOKED},
    )