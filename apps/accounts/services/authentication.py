import uuid

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.choices import AuthType
from apps.accounts.models import DeviceSession
from apps.accounts.services.realtime import broadcast_session_revoked 


@transaction.atomic
def create_device_session(
    *,
    user,
    device_name="",
    device_type="",
    user_agent="",
):
    """Create one device session (API/JWT login) and issue its JWT token pair."""
    session_id = uuid.uuid4()
    now = timezone.now()

    refresh = RefreshToken.for_user(user)
    refresh["sid"] = str(session_id)
    access = refresh.access_token

    session = DeviceSession.objects.create(
        id=session_id,
        user=user,
        auth_type=AuthType.API,
        device_name=device_name[:100],
        device_type=device_type[:30],
        user_agent=user_agent,
        refresh_token_jti=refresh["jti"],
        expires_at=now + refresh.lifetime,
        last_used_at=now,
    )

    return {
        "access": str(access),
        "refresh": str(refresh),
        "session": session,
    }


@transaction.atomic
def create_web_device_session(
    *,
    user,
    django_session_key,
    expires_at,
    device_name="",
    device_type="",
    user_agent="",
):
    """
    Create one device session for a session-cookie (web/HTMX) login.

    Unlike create_device_session, there's no JWT here — Django's own
    session framework is already what keeps the browser logged in.
    django_session_key is what lets revoke_device_session later find
    and delete the actual django.contrib.sessions.models.Session row
    for this browser, so "remove this device" genuinely logs it out
    instead of just flipping a DB flag nothing enforces.

    Called from apps.accounts.views.authentication.login_view right
    after django.contrib.auth.login(), using
    request.session.session_key and request.session.get_expiry_date().
    """
    session = DeviceSession.objects.create(
        id=uuid.uuid4(),
        user=user,
        auth_type=AuthType.WEB,
        django_session_key=django_session_key,
        device_name=device_name[:100],
        device_type=device_type[:30],
        user_agent=user_agent,
        expires_at=expires_at,
        last_used_at=timezone.now(),
    )

    return session


@transaction.atomic
def revoke_device_session(*, session):
    """
    Revoke a device session.

    Enforcement differs by auth_type (see apps.accounts.choices.AuthType
    for why): API sessions get their refresh token blacklisted; web
    sessions get their underlying Django Session row deleted outright,
    since there's no token to blacklist.
    """
    session = DeviceSession.objects.select_for_update().get(pk=session.pk)

    if session.revoked_at is not None:
        return session

    if session.auth_type == AuthType.API and session.refresh_token_jti:
        outstanding = OutstandingToken.objects.filter(jti=session.refresh_token_jti).first()
        if outstanding is not None:
            BlacklistedToken.objects.get_or_create(token=outstanding)
    elif session.auth_type == AuthType.WEB and session.django_session_key:
        Session.objects.filter(session_key=session.django_session_key).delete()

    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at", "updated_at"])

    # Deferred to on_commit: if this transaction rolls back, we must
    # not have already told open WebSockets to disconnect for a
    # revoke that never actually happened.
    transaction.on_commit(lambda: broadcast_session_revoked(session_id=session.id))

    return session


@transaction.atomic
def revoke_all_device_sessions(*, user, except_session_id=None):
    """Revoke all active device sessions for a user, optionally keeping one."""
    queryset = DeviceSession.objects.select_for_update().filter(
        user=user,
        revoked_at__isnull=True,
    )

    if except_session_id is not None:
        queryset = queryset.exclude(pk=except_session_id)

    sessions = list(queryset)
    for session in sessions:
        revoke_device_session(session=session)

    return len(sessions)


