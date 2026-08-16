from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services.realtime import broadcast_presence_change
from apps.common.redis_client import redis_client

HEARTBEAT_INTERVAL_SECONDS = 20
HEARTBEAT_TTL_SECONDS = 45


def _connections_key(user_id):
    """Redis SET of channel_names currently open for this user — source of truth for 'is this user online right now'."""
    return f'presence:connections:{user_id}'


def _heartbeat_key(channel_name):
    """
    A Redis STRING with a TTL, one per open connection. If the process
    behind it crashes or the dev server restarts without a clean
    disconnect, this key simply expires on its own — no manual cleanup
    needed. reap_stale_connections uses its ABSENCE to detect that.
    """
    return f'presence:heartbeat:{channel_name}'


async def register_connection(*, user_id, channel_name):
    added = await redis_client.sadd(_connections_key(user_id), channel_name)
    await redis_client.set(_heartbeat_key(channel_name), '1', ex=HEARTBEAT_TTL_SECONDS)

    if added and await redis_client.scard(_connections_key(user_id)) == 1:
        await User.objects.filter(id=user_id).aupdate(is_online=True)
        await broadcast_presence_change(user_id=user_id, is_online=True)


async def refresh_heartbeat(*, channel_name):
    await redis_client.set(_heartbeat_key(channel_name), '1', ex=HEARTBEAT_TTL_SECONDS)


async def unregister_connection(*, user_id, channel_name):
    await redis_client.delete(_heartbeat_key(channel_name))
    await redis_client.srem(_connections_key(user_id), channel_name)

    if await redis_client.scard(_connections_key(user_id)) == 0:
        await _mark_offline(user_id=user_id)


async def reap_stale_connections():
    """
    Periodic sweep (called by the presence_reaper management command):
    removes any channel_name whose heartbeat key expired — meaning the
    process behind it died without calling disconnect() (exactly the
    dev-server-restart scenario that caused this bug). This is what
    self-heals the Redis Set instead of letting it drift forever.
    """
    async for key in redis_client.scan_iter(match='presence:connections:*'):
        user_id = key.split(':')[-1]
        channel_names = await redis_client.smembers(key)

        for channel_name in channel_names:
            if not await redis_client.exists(_heartbeat_key(channel_name)):
                await redis_client.srem(key, channel_name)

        if await redis_client.scard(key) == 0:
            await _mark_offline(user_id=user_id)


async def _mark_offline(*, user_id):
    last_seen = timezone.now()
    await User.objects.filter(id=user_id).aupdate(is_online=False, last_seen=last_seen)
    await broadcast_presence_change(user_id=user_id, is_online=False, last_seen=last_seen)