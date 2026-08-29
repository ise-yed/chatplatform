from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.api.v1.serializers import MessageSerializer, SendMessageSerializer
from apps.chat.permissions import IsConversationParticipant
from apps.chat.selectors import get_messages_for_conversation
from apps.chat.services import send_message
from apps.common.pagination import MessageCursorPagination


class MessageListCreateApi(APIView):
    """
    GET: لیست پیام‌های یه گفتگوی مشخص.
    POST: فرستادن پیام جدید در همون گفتگو.
    """
    permission_classes = [IsAuthenticated, IsConversationParticipant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, conversation_id):
        messages = get_messages_for_conversation(conversation_id=conversation_id)

        # Cursor-paginate so we never serialize an entire (unbounded)
        # conversation history in one response. The paginator applies
        # its own '-created_at' ordering; `next` walks into older messages.
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request, view=self)
        serializer = MessageSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, conversation_id):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = send_message(
            conversation_id=conversation_id,
            sender=request.user,
            message_type=serializer.validated_data.get('type'),
            content=serializer.validated_data.get('content', ''),
            attachment=serializer.validated_data.get('attachment'),
        )

        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )