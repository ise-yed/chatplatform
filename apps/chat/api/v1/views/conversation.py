from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.chat.api.v1.serializers import ConversationListSerializer, CreateDirectConversationSerializer
from apps.chat.selectors import get_conversations_for_user
from apps.chat.services import create_direct_conversation


class ConversationListCreateApi(APIView):
    """
    GET: لیست گفتگوهای کاربر لاگین‌شده.
    POST: ساخت یه گفتگوی دو نفره‌ی جدید با یه کاربر دیگر.
    """

    def get(self, request):
        conversations = get_conversations_for_user(user=request.user)
        serializer = ConversationListSerializer(conversations, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CreateDirectConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        other_user = User.objects.filter(id=serializer.validated_data['other_user_id']).first()
        if other_user is None:
            raise NotFound('User not found.')

        conversation = create_direct_conversation(creator=request.user, other_user=other_user)
        return Response(
            ConversationListSerializer(conversation).data, status=status.HTTP_201_CREATED
        )