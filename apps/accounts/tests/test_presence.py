import pytest

from apps.accounts.models import User
from apps.accounts.services.presence import (
    HEARTBEAT_TTL_SECONDS,
    _connections_key,
    _heartbeat_key,
    reap_stale_connections,
    refresh_heartbeat,
    register_connection,
    unregister_connection,
)
from apps.common.redis_client import redis_client


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def user_a(db):
    return User.objects.create_user(
        username="presence_user",
        password="pass12345",
    )


@pytest.fixture(autouse=True)
def mock_presence_broadcast(monkeypatch):
    async def _mock_broadcast(**kwargs):
        return None

    monkeypatch.setattr(
        "apps.accounts.services.presence.broadcast_presence_change",
        _mock_broadcast,
    )


@pytest.mark.asyncio
async def test_register_first_connection_marks_user_online(user_a):
    await redis_client.flushdb()

    channel_name = "channel-1"

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_name,
    )

    await user_a.arefresh_from_db()

    assert user_a.is_online is True

    connections = await redis_client.smembers(
        _connections_key(user_a.id)
    )

    assert connections == {channel_name}

    heartbeat_key = _heartbeat_key(channel_name)

    assert await redis_client.exists(heartbeat_key) == 1

    ttl = await redis_client.ttl(heartbeat_key)

    assert 0 < ttl <= HEARTBEAT_TTL_SECONDS


@pytest.mark.asyncio
async def test_register_second_connection_keeps_user_online(user_a):
    await redis_client.flushdb()

    channel_1 = "channel-1"
    channel_2 = "channel-2"

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_1,
    )

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_2,
    )

    await user_a.arefresh_from_db()

    assert user_a.is_online is True

    connections = await redis_client.smembers(
        _connections_key(user_a.id)
    )

    assert connections == {
        channel_1,
        channel_2,
    }


@pytest.mark.asyncio
async def test_register_same_connection_twice_does_not_duplicate_it(user_a):
    await redis_client.flushdb()

    channel_name = "channel-1"

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_name,
    )

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_name,
    )

    connections = await redis_client.smembers(
        _connections_key(user_a.id)
    )

    assert connections == {channel_name}

    assert await redis_client.scard(
        _connections_key(user_a.id)
    ) == 1


@pytest.mark.asyncio
async def test_refresh_heartbeat_refreshes_ttl(user_a):
    await redis_client.flushdb()

    channel_name = "channel-1"

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_name,
    )

    heartbeat_key = _heartbeat_key(channel_name)

    ttl_before = await redis_client.ttl(heartbeat_key)

    assert ttl_before > 0

    await refresh_heartbeat(
        channel_name=channel_name,
    )

    ttl_after = await redis_client.ttl(heartbeat_key)

    assert ttl_after > 0
    assert ttl_after <= HEARTBEAT_TTL_SECONDS


@pytest.mark.asyncio
async def test_unregister_one_connection_keeps_user_online(user_a):
    await redis_client.flushdb()

    channel_1 = "channel-1"
    channel_2 = "channel-2"

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_1,
    )

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_2,
    )

    await unregister_connection(
        user_id=user_a.id,
        channel_name=channel_1,
    )

    await user_a.arefresh_from_db()

    assert user_a.is_online is True

    connections = await redis_client.smembers(
        _connections_key(user_a.id)
    )

    assert connections == {channel_2}

    assert await redis_client.exists(
        _heartbeat_key(channel_1)
    ) == 0

    assert await redis_client.exists(
        _heartbeat_key(channel_2)
    ) == 1


@pytest.mark.asyncio
async def test_unregister_last_connection_marks_user_offline(user_a):
    await redis_client.flushdb()

    channel_name = "channel-1"

    await register_connection(
        user_id=user_a.id,
        channel_name=channel_name,
    )

    await unregister_connection(
        user_id=user_a.id,
        channel_name=channel_name,
    )

    await user_a.arefresh_from_db()

    assert user_a.is_online is False
    assert user_a.last_seen is not None

    connections = await redis_client.smembers(
        _connections_key(user_a.id)
    )

    assert connections == set()

    assert await redis_client.exists(
        _heartbeat_key(channel_name)
    ) == 0


@pytest.mark.asyncio
async def test_reaper_removes_stale_connection(user_a):
    await redis_client.flushdb()

    channel_name = "stale-channel"

    connections_key = _connections_key(user_a.id)
    heartbeat_key = _heartbeat_key(channel_name)

    await redis_client.sadd(
        connections_key,
        channel_name,
    )

    assert await redis_client.exists(heartbeat_key) == 0

    await User.objects.filter(
        id=user_a.id
    ).aupdate(is_online=True)

    await reap_stale_connections()

    connections = await redis_client.smembers(
        connections_key
    )

    assert connections == set()

    await user_a.arefresh_from_db()

    assert user_a.is_online is False
    assert user_a.last_seen is not None


@pytest.mark.asyncio
async def test_reaper_keeps_user_online_if_active_connection_exists(user_a):
    await redis_client.flushdb()

    stale_channel = "stale-channel"
    active_channel = "active-channel"

    connections_key = _connections_key(user_a.id)

    await redis_client.sadd(
        connections_key,
        stale_channel,
        active_channel,
    )

    await redis_client.set(
        _heartbeat_key(active_channel),
        "1",
        ex=HEARTBEAT_TTL_SECONDS,
    )

    await User.objects.filter(
        id=user_a.id
    ).aupdate(is_online=True)

    await reap_stale_connections()

    connections = await redis_client.smembers(
        connections_key
    )

    assert connections == {active_channel}

    await user_a.arefresh_from_db()

    assert user_a.is_online is True

    assert await redis_client.exists(
        _heartbeat_key(active_channel)
    ) == 1