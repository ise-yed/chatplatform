from django.urls import path

from apps.chat.api.v1.views import ConversationListCreateApi, MessageListCreateApi

app_name = 'chat_api_v1'

urlpatterns = [
    path('conversations/', ConversationListCreateApi.as_view(), name='conversation-list-create'),
    path('conversations/<uuid:conversation_id>/messages/', MessageListCreateApi.as_view(), name='message-list-create'),
]