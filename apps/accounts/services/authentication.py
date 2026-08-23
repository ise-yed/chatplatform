import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

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
    """Create one device session and issue its JWT token pair."""
    session_id = uuid.uuid4()
    now = timezone.now()

    refresh = RefreshToken.for_user(user)
    refresh["sid"] = str(session_id)
    access = refresh.access_token

    session = DeviceSession.objects.create(
        id=session_id,
        user=user,
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
def revoke_device_session(*, session):
    """Revoke a device session and blacklist its current refresh token."""
    session = DeviceSession.objects.select_for_update().get(pk=session.pk)

    if session.revoked_at is not None:
        return session

    outstanding = OutstandingToken.objects.filter(jti=session.refresh_token_jti).first()
    if outstanding is not None:
        BlacklistedToken.objects.get_or_create(token=outstanding)

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
