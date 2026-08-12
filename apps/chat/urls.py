from django.urls import path

from apps.chat.views.conversation import conversation_list_view
from apps.chat.views.message import conversation_detail_view, send_message_view

app_name = 'chat'

urlpatterns = [
    path('', conversation_list_view, name='conversation_list'),
    path('<uuid:conversation_id>/', conversation_detail_view, name='conversation_detail'),
    path('<uuid:conversation_id>/send/', send_message_view, name='send_message'),
]