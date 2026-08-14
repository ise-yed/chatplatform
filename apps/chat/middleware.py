from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_from_token(token):
    """Resolves a JWT access token (from the mobile app) into a User instance."""
    from apps.accounts.models import User

    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Fallback authentication for WebSocket connections that arrive
    WITHOUT a valid Django session — i.e. the mobile app, which has
    no cookie and instead sends a JWT via the ?token= query param.

    This middleware must run AFTER channels.auth.AuthMiddlewareStack
    in the asgi.py chain, so that scope['user'] is already populated
    from the session cookie for browser (HTMX) connections. If the
    session already resolved a real user, this middleware does
    nothing — it only kicks in when scope['user'] is still Anonymous.
    """

    async def __call__(self, scope, receive, send):
        current_user = scope.get('user')

        if current_user is None or current_user.is_anonymous:
            query_params = parse_qs(scope['query_string'].decode())
            token = query_params.get('token', [None])[0]
            scope['user'] = await get_user_from_token(token) if token else AnonymousUser()

        return await super().__call__(scope, receive, send)