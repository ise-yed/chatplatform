from django.urls import path

from apps.accounts.consumers import PresenceConsumer

websocket_urlpatterns = [
    path('ws/presence/', PresenceConsumer.as_asgi()),
]