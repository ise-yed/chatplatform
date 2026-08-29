import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from apps.accounts.routing import (
    websocket_urlpatterns as accounts_websocket_urlpatterns,
)
from apps.chat.middleware import JWTAuthMiddleware
from apps.chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    # AllowedHostsOriginValidator rejects WebSocket handshakes whose Origin
    # header isn't in ALLOWED_HOSTS, before any auth runs. Without it any
    # website could open an authenticated socket against us using the
    # visitor's session cookie (cross-site WebSocket hijacking).
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            JWTAuthMiddleware(URLRouter(accounts_websocket_urlpatterns + chat_websocket_urlpatterns))
        )
    ),
})