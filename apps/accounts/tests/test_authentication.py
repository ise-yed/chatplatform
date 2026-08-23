import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.test import override_settings
from apps.accounts.models import DeviceSession

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def disable_login_throttle(settings):
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"] = "1000/min"
@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return __import__('apps.accounts.models', fromlist=['User']).User.objects.create_user(
        username='mort', password='strong-password-123'
    )


def login(client, username='mort', password='strong-password-123', device_name='Laptop', device_type='desktop'):
    return client.post(
        '/api/v1/accounts/login/',
        {
            'username': username,
            'password': password,
            'device_name': device_name,
            'device_type': device_type,
        },
        format='json',
    )


def test_login_creates_one_device_session(api_client, user):
    response = login(api_client)

    assert response.status_code == status.HTTP_200_OK
    assert DeviceSession.objects.filter(user=user, revoked_at__isnull=True).count() == 1
    session = DeviceSession.objects.get(user=user)
    assert response.data['session']['id'] == str(session.id)
    assert session.refresh_token_jti


def test_login_from_two_devices_creates_two_sessions(api_client, user):
    first = login(api_client, device_name='Laptop')
    second = login(api_client, device_name='Phone', device_type='mobile')

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert DeviceSession.objects.filter(user=user, revoked_at__isnull=True).count() == 2


def test_refresh_rotates_refresh_token_and_updates_session(api_client, user):
    login_response = login(api_client)
    old_refresh = login_response.data['tokens']['refresh']
    session_id = login_response.data['session']['id']
    old_session_jti = DeviceSession.objects.get(id=session_id).refresh_token_jti

    response = api_client.post(
        '/api/v1/accounts/refresh/',
        {'refresh': old_refresh},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert 'access' in response.data
    assert 'refresh' in response.data

    session = DeviceSession.objects.get(id=session_id)
    assert session.refresh_token_jti != old_session_jti

    reused = api_client.post(
        '/api/v1/accounts/refresh/',
        {'refresh': old_refresh},
        format='json',
    )
    assert reused.status_code == status.HTTP_400_BAD_REQUEST


def test_logout_revokes_only_current_device_session(api_client, user):
    first = login(api_client, device_name='Laptop')
    second = login(api_client, device_name='Phone')

    access = first.data['tokens']['access']
    first_session_id = first.data['session']['id']
    second_session_id = second.data['session']['id']

    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    response = api_client.post('/api/v1/accounts/logout/', format='json')

    assert response.status_code == status.HTTP_200_OK
    assert DeviceSession.objects.get(id=first_session_id).revoked_at is not None
    assert DeviceSession.objects.get(id=second_session_id).revoked_at is None


def test_logout_all_revokes_all_device_sessions(api_client, user):
    login(api_client, device_name='Laptop')
    second = login(api_client, device_name='Phone')

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {second.data['tokens']['access']}")
    response = api_client.post('/api/v1/accounts/logout-all/', format='json')

    assert response.status_code == status.HTTP_200_OK
    assert DeviceSession.objects.filter(user=user, revoked_at__isnull=True).count() == 0


@pytest.mark.django_db(transaction=True)
def test_logout_broadcasts_session_revoked_for_that_session_only(api_client, user, monkeypatch):
    """
    Revoking a session must force-disconnect any open WebSocket tied to
    it (see apps.accounts.services.realtime.broadcast_session_revoked),
    not just block future token refreshes.

    Uses transaction=True: broadcast_session_revoked is fired via
    transaction.on_commit, which never runs inside the rolled-back
    transaction pytest-django's plain django_db fixture wraps tests in.
    """
    revoked_session_ids = []
    monkeypatch.setattr(
        'apps.accounts.services.authentication.broadcast_session_revoked',
        lambda *, session_id: revoked_session_ids.append(str(session_id)),
    )

    first = login(api_client, device_name='Laptop')
    login(api_client, device_name='Phone')
    first_session_id = first.data['session']['id']

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {first.data['tokens']['access']}")
    response = api_client.post('/api/v1/accounts/logout/', format='json')

    assert response.status_code == status.HTTP_200_OK
    assert revoked_session_ids == [first_session_id]


@pytest.mark.django_db(transaction=True)
def test_logout_all_broadcasts_session_revoked_for_every_session(api_client, user, monkeypatch):
    revoked_session_ids = []
    monkeypatch.setattr(
        'apps.accounts.services.authentication.broadcast_session_revoked',
        lambda *, session_id: revoked_session_ids.append(str(session_id)),
    )

    first = login(api_client, device_name='Laptop')
    second = login(api_client, device_name='Phone')

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {second.data['tokens']['access']}")
    api_client.post('/api/v1/accounts/logout-all/', format='json')

    assert set(revoked_session_ids) == {
        first.data['session']['id'],
        second.data['session']['id'],
    }


@pytest.mark.django_db(transaction=True)
def test_broadcast_session_revoked_not_called_when_session_already_revoked(api_client, user, monkeypatch):
    """revoke_device_session is a no-op (and shouldn't re-broadcast) for an already-revoked session."""
    revoked_session_ids = []
    monkeypatch.setattr(
        'apps.accounts.services.authentication.broadcast_session_revoked',
        lambda *, session_id: revoked_session_ids.append(str(session_id)),
    )

    first = login(api_client, device_name='Laptop')
    session_id = first.data['session']['id']

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {first.data['tokens']['access']}")
    api_client.post('/api/v1/accounts/logout/', format='json')
    api_client.post('/api/v1/accounts/logout/', format='json')  # second call: session already revoked

    assert revoked_session_ids == [session_id]
