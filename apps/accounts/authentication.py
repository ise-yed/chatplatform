from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import DeviceSession


class DeviceSessionAuthentication(JWTAuthentication):
    """
    JWTAuthentication, plus a DeviceSession check on every request.

    By default, JWTAuthentication only verifies the access token's
    signature and expiry — it never checks simplejwt's blacklist,
    which only applies to refresh tokens. That means revoking a
    DeviceSession (single-session revoke, or "log out everywhere")
    used to leave that device's already-issued access token working
    on every authenticated endpoint for up to
    SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] (currently 15 minutes) —
    revoke wasn't actually immediate.

    This overrides get_user() to additionally look up the DeviceSession
    referenced by the token's "sid" claim (added in
    apps.accounts.services.authentication.create_device_session and
    copied from refresh token to access token automatically by
    simplejwt) and reject the request if that session isn't active —
    reusing DeviceSession.is_active, the same property the WebSocket
    middleware (apps.chat.middleware) and DeviceSessionSerializer rely
    on, so this can't silently drift out of sync with those.

    Tokens with no "sid" claim (issued before this field existed, or
    obtained some other way) are let through unchanged — there's no
    session to check.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        session_id = validated_token.get("sid")
        if session_id is None:
            return user

        session = DeviceSession.objects.filter(id=session_id, user=user).first()

        if session is None:
            raise AuthenticationFailed("Device session not found.", code="session_not_found")

        if not session.is_active:
            raise AuthenticationFailed("Device session is revoked or expired.", code="session_revoked")

        return user
