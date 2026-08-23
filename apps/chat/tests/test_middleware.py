from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.accounts.services.authentication import create_device_session, revoke_device_session
from apps.chat.middleware import get_user_and_session_from_token

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture(autouse=True)
def mock_session_revoked_broadcast(monkeypatch):
    """Keeps these tests off the real Redis channel layer — same reasoning as conftest's mock_broadcast."""
    monkeypatch.setattr('apps.accounts.services.authentication.broadcast_session_revoked', lambda **kwargs: None)


@pytest.mark.asyncio
async def test_valid_token_returns_user_and_session_id(user_a):
    result = await database_sync_to_async(create_device_session)(user=user_a)
    access_token = result['access']
    session_id = result['session'].id

    user, session_id_from_token = await get_user_and_session_from_token(access_token)

    assert user == user_a
    assert session_id_from_token == str(session_id)


@pytest.mark.asyncio
async def test_revoked_session_rejects_the_token(user_a):
    result = await database_sync_to_async(create_device_session)(user=user_a)
    await database_sync_to_async(revoke_device_session)(session=result['session'])

    user, session_id = await get_user_and_session_from_token(result['access'])

    assert isinstance(user, AnonymousUser)
    assert session_id is None


@pytest.mark.asyncio
async def test_expired_session_rejects_the_token(user_a):
    result = await database_sync_to_async(create_device_session)(user=user_a)
    session = result['session']

    def _expire_session():
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save(update_fields=['expires_at'])

    await database_sync_to_async(_expire_session)()

    user, session_id = await get_user_and_session_from_token(result['access'])

    assert isinstance(user, AnonymousUser)
    assert session_id is None


@pytest.mark.asyncio
async def test_garbage_token_returns_anonymous_user():
    user, session_id = await get_user_and_session_from_token('not-a-real-token')

    assert isinstance(user, AnonymousUser)
    assert session_id is None
