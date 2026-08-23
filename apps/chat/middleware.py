from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_and_session_from_token(token):
    """
    Resolves a JWT access token into (User, session_id).

    Unlike DRF's JWTAuthentication (used for regular API requests),
    this also verifies the DeviceSession tied to the token's "sid"
    claim is still active. Without this check, a WebSocket could be
    opened with an access token belonging to a session the user had
    already revoked (e.g. from the "my devices" screen) — the token
    itself would still verify fine since access tokens aren't
    blacklisted, only refresh tokens are.

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
        session_is_active = DeviceSession.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
            id=session_id,
            revoked_at__isnull=True,
        ).exists()

        if not session_is_active:
            return AnonymousUser(), None

    return user, session_id


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
    does nothing — it only kicks in when scope['user'] is still Anonymous.
    """

    async def __call__(self, scope, receive, send):
        current_user = scope.get('user')
        # session_id is only ever set for JWT-authenticated connections
        # (see get_user_and_session_from_token). Session-cookie logins
        # don't have a DeviceSession yet, so there's nothing to force-
        # disconnect them by — default to None so consumers can safely
        # call scope.get('session_id') either way.
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
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                elif auth_header.startswith('Token '):
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

        return await super().__call__(scope, receive, send)