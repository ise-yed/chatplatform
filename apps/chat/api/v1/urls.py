from django.urls import path

from apps.chat.api.v1.views import (
    ConversationListCreateApi,
    GroupConversationCreateApi,
    GroupLeaveApi,
    GroupParticipantDeleteApi,
    GroupParticipantListCreateApi,
    MessageListCreateApi,
)

app_name = 'chat_api_v1'


urlpatterns = [
    path('conversations/', ConversationListCreateApi.as_view(), name='conversation-list-create'),
    path('conversations/groups/', GroupConversationCreateApi.as_view(), name='group-conversation-create'),
    path('conversations/<uuid:conversation_id>/messages/', MessageListCreateApi.as_view(), name='message-list-create'),
    path('conversations/<uuid:conversation_id>/participants/', GroupParticipantListCreateApi.as_view(), name='group-participant-list-create'),
    path('conversations/<uuid:conversation_id>/participants/<uuid:user_id>/', GroupParticipantDeleteApi.as_view(), name='group-participant-delete'),
    path('conversations/<uuid:conversation_id>/leave/', GroupLeaveApi.as_view(), name='group-leave'),
]