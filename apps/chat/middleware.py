from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_and_session_from_token(token):
    """
    Resolves a JWT access token into (User, session_id).

    Also verifies the DeviceSession tied to the token's "sid" claim is
    still active (same DeviceSession.is_active property used by
    apps.accounts.authentication.DeviceSessionAuthentication for
    regular API requests, and by DeviceSessionSerializer) — a
    WebSocket shouldn't be openable with an access token belonging to
    an already-revoked session any more than a REST call should.

    Returns (AnonymousUser(), None) for any invalid, expired, or
    revoked case so the caller has one failure path to handle.
    """
    from apps.accounts.models import DeviceSession, User

    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        session_id = access_token.get('sid')
    except (InvalidToken, TokenError):
        return AnonymousUser(), None

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser(), None

    if session_id is not None:
        session = DeviceSession.objects.filter(id=session_id, user=user).first()
        if session is None or not session.is_active:
            return AnonymousUser(), None

    return user, session_id


@database_sync_to_async
def get_device_session_id_for_cookie_user(*, user, django_session_key):
    """
    Resolves a cookie-authenticated (web/HTMX) connection's Django
    session key to its DeviceSession id.

    Cookie-authenticated connections have no JWT "sid" claim to read,
    but create_web_device_session (apps.accounts.services.authentication)
    stores the Django session_key on the DeviceSession precisely so it
    can be looked up here. Without this, a web WebSocket would never
    join device_session_group() and broadcast_session_revoked() would
    have no open connection to reach — "remove this device" would only
    take effect on that browser's next plain HTTP request, not on an
    already-open socket.

    Returns None if there's no django_session_key (shouldn't happen for
    a genuinely cookie-authenticated scope) or no matching active
    DeviceSession.
    """
    if not django_session_key:
        return None

    from apps.accounts.models import DeviceSession

    session = DeviceSession.objects.filter(user=user, django_session_key=django_session_key).first()
    if session is None or not session.is_active:
        return None

    return str(session.id)


class JWTAuthMiddleware(BaseMiddleware):
    """
    Authentication middleware for WebSocket connections.
    
    Supports multiple authentication methods:
    1. Session cookie (for browser/HTMX) - handled by AuthMiddlewareStack
    2. JWT via query parameter (for mobile web views) - ?token=...
    3. JWT via Authorization header (for Postman, Flutter, mobile apps) - Bearer token
    
    This middleware runs AFTER channels.auth.AuthMiddlewareStack in asgi.py,
    so scope['user'] is already populated from session cookie for browser
    connections. If session already resolved a real user, this middleware
    only resolves that connection's DeviceSession id (see
    get_device_session_id_for_cookie_user) — it re-authenticates only when
    scope['user'] is still Anonymous.
    """

    async def __call__(self, scope, receive, send):
        current_user = scope.get('user')
        # session_id is what lets consumers join device_session_group()
        # so broadcast_session_revoked() can force-close them — see
        # apps.chat.consumers.ChatConsumer and apps.accounts.consumers.PresenceConsumer.
        scope.setdefault('session_id', None)

        # فقط اگر کاربر از طریق session احراز هویت نشده باشد
        if current_user is None or current_user.is_anonymous:
            token = None
            
            # 1️⃣ اول: از Query String دریافت کن (روش فعلی برای وب)
            query_params = parse_qs(scope['query_string'].decode())
            token = query_params.get('token', [None])[0]
            
            # 2️⃣ دوم: اگر در Query نبود، از Header Authorization دریافت کن
            if not token:
                headers = dict(scope.get('headers', []))
                auth_header = headers.get(b'authorization', b'').decode()
                
                # پشتیبانی از هر دو فرمت Bearer و Token
                if auth_header.startswith('Bearer ') or auth_header.startswith('Token '):
                    token = auth_header.split(' ')[1]
            
            # 3️⃣ سوم: (اختیاری) از Cookie دریافت کن
            if not token:
                cookies = scope.get('cookies', {})
                token = cookies.get('token') or cookies.get('access_token')
            
            # اگر توکن پیدا شد، کاربر را احراز هویت کن
            if token:
                scope['user'], scope['session_id'] = await get_user_and_session_from_token(token)
            else:
                scope['user'] = AnonymousUser()
        else:
            # AuthMiddlewareStack already resolved a user from the
            # session cookie. django_session's row was already deleted
            # by revoke_device_session if that session had been revoked,
            # so AuthMiddlewareStack would have failed to resolve a user
            # in that case — we wouldn't even get here. What's still
            # missing is the DeviceSession id itself, for group_add().
            django_session = scope.get('session')
            django_session_key = getattr(django_session, 'session_key', None)
            scope['session_id'] = await get_device_session_id_for_cookie_user(
                user=current_user, django_session_key=django_session_key,
            )

        return await super().__call__(scope, receive, send)