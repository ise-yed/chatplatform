import pytest
from django.contrib.sessions.models import Session
from django.test import Client

from apps.accounts.choices import AuthType
from apps.accounts.models import DeviceSession, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(username='mort', password='strong-password-123')


def test_web_login_creates_a_device_session(user):
    client = Client()
    response = client.post('/accounts/login/', {'username': 'mort', 'password': 'strong-password-123'})

    assert response.status_code == 302
    session = DeviceSession.objects.get(user=user)
    assert session.auth_type == AuthType.WEB
    assert session.django_session_key == client.session.session_key
    assert session.refresh_token_jti is None
    assert session.revoked_at is None


def test_web_login_device_session_shows_up_alongside_api_sessions(user):
    """This is the actual point of the fix: a "my devices" view built on DeviceSession must see web logins too, not just API/mobile ones."""
    client = Client()
    client.post('/accounts/login/', {'username': 'mort', 'password': 'strong-password-123'})

    sessions = DeviceSession.objects.filter(user=user, revoked_at__isnull=True)
    assert sessions.count() == 1
    assert sessions.first().auth_type == AuthType.WEB


def test_web_logout_revokes_the_device_session(user):
    client = Client()
    client.post('/accounts/login/', {'username': 'mort', 'password': 'strong-password-123'})
    session = DeviceSession.objects.get(user=user)

    client.post('/accounts/logout/')

    session.refresh_from_db()
    assert session.revoked_at is not None


def test_web_logout_deletes_the_underlying_django_session(user):
    """
    revoke_device_session must actually delete the Session row for a
    web session — that's what makes revoke effective on the browser's
    very next request, since Django's session auth doesn't consult
    DeviceSession on its own.
    """
    client = Client()
    client.post('/accounts/login/', {'username': 'mort', 'password': 'strong-password-123'})
    session_key = client.session.session_key
    assert Session.objects.filter(session_key=session_key).exists()

    client.post('/accounts/logout/')

    assert not Session.objects.filter(session_key=session_key).exists()


def test_revoking_a_web_session_from_elsewhere_logs_that_browser_out(user):
    """
    Simulates "remove this device" from a dashboard on a *different*
    browser/tab: revoking the DeviceSession directly (not via this
    browser's own logout) must still kill the original browser's
    session on its next request.
    """
    from apps.accounts.services.authentication import revoke_device_session

    client = Client()
    client.post('/accounts/login/', {'username': 'mort', 'password': 'strong-password-123'})
    session = DeviceSession.objects.get(user=user)

    revoke_device_session(session=session)

    # Same browser client, no new login — its session cookie is now orphaned.
    response = client.get('/chat/')
    assert response.wsgi_request.user.is_authenticated is False
