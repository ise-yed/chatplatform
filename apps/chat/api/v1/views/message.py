from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.permissions import IsConversationParticipant
from apps.chat.api.v1.serializers import MessageSerializer, SendMessageSerializer
from apps.chat.selectors import get_messages_for_conversation
from apps.chat.services import send_message


class MessageListCreateApi(APIView):
    """
    GET: لیست پیام‌های یه گفتگوی مشخص.
    POST: فرستادن پیام جدید در همون گفتگو.
    """
    permission_classes = [IsAuthenticated, IsConversationParticipant]

    def get(self, request, conversation_id):
        messages = get_messages_for_conversation(conversation_id=conversation_id)
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, conversation_id):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = send_message(
            conversation_id=conversation_id,
            sender=request.user,
            content=serializer.validated_data['content'],
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)