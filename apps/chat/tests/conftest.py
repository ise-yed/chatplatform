import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


@pytest.fixture
def user_a(db):
    """A user who will act as the conversation creator in most tests."""
    return User.objects.create_user(username='user_a', password='pass12345')


@pytest.fixture
def user_b(db):
    """A user who will act as the second participant in most tests."""
    return User.objects.create_user(username='user_b', password='pass12345')


@pytest.fixture
def outsider(db):
    """A user who is never a participant — used to test access control."""
    return User.objects.create_user(username='outsider', password='pass12345')


@pytest.fixture
def api_client():
    """A plain DRF APIClient with no authentication set."""
    return APIClient()


@pytest.fixture
def auth_client(api_client):
    """Returns a function that authenticates the given client as a given user via JWT."""

    def _authenticate(user):
        access_token = RefreshToken.for_user(user).access_token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        return api_client

    return _authenticate


@pytest.fixture(autouse=True)
def mock_broadcast(monkeypatch):
    """
    Keeps every test in this app from touching the real Redis channel
    layer. Broadcasting itself will be covered separately in
    test_consumers.py (Phase 13) using WebsocketCommunicator — these
    tests only care about DB writes, query correctness, and
    HTTP/permission behavior.
    """
    monkeypatch.setattr('apps.chat.services.message.broadcast_new_message', lambda **kwargs: None)