from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.chat.api.v1.serializers import (
    AddParticipantSerializer,
    ConversationListSerializer,
    CreateDirectConversationSerializer,
    CreateGroupConversationSerializer,
    GroupParticipantSerializer,
)
from apps.chat.permissions import IsConversationAdmin, IsConversationParticipant
from apps.chat.selectors import get_conversations_for_user, get_group_participants
from apps.chat.services import (
    add_participant,
    create_direct_conversation,
    create_group_conversation,
    leave_conversation,
    remove_participant,
)
from apps.common.pagination import StandardResultsSetPagination


class ConversationListCreateApi(APIView):
    """
    GET: لیست گفتگوهای کاربر لاگین‌شده.
    POST: ساخت یه گفتگوی دو نفره‌ی جدید با یه کاربر دیگر.
    """

    def get(self, request):
        conversations = get_conversations_for_user(user=request.user)

        # Paginate so a user with a large number of conversations doesn't
        # force us to serialize them all in one response. The queryset is
        # already ordered newest-activity-first (Conversation.Meta ordering
        # = -updated_at), which the send_message service keeps fresh.
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(conversations, request, view=self)
        serializer = ConversationListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

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
        
        
        

class GroupConversationCreateApi(APIView):
    """POST: ساخت گفتگوی گروهی جدید. سازنده خودکار ADMIN می‌شه."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # چون avatar فایله

    def post(self, request):
        serializer = CreateGroupConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation = create_group_conversation(
            creator=request.user,
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('description', ''),
            avatar=serializer.validated_data.get('avatar'),
            participant_ids=serializer.validated_data.get('participant_ids', []),
        )
        return Response(ConversationListSerializer(conversation).data, status=status.HTTP_201_CREATED)


class GroupParticipantListCreateApi(APIView):
    """GET: لیست اعضا (هر عضوی می‌بینه). POST: اضافه‌کردن عضو (فقط ادمین)."""

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsConversationAdmin()]
        return [IsAuthenticated(), IsConversationParticipant()]

    def get(self, request, conversation_id):
        participants = get_group_participants(conversation_id=conversation_id)
        return Response(GroupParticipantSerializer(participants, many=True).data)

    def post(self, request, conversation_id):
        serializer = AddParticipantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(id=serializer.validated_data['user_id']).first()
        if user is None:
            raise NotFound('User not found.')

        add_participant(conversation_id=conversation_id, actor=request.user, user=user)
        participants = get_group_participants(conversation_id=conversation_id)
        return Response(GroupParticipantSerializer(participants, many=True).data, status=status.HTTP_201_CREATED)


class GroupParticipantDeleteApi(APIView):
    """DELETE: حذف یه عضو از گروه (فقط ادمین)."""
    permission_classes = [IsAuthenticated, IsConversationAdmin]

    def delete(self, request, conversation_id, user_id):
        remove_participant(conversation_id=conversation_id, actor=request.user, user_id=user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupLeaveApi(APIView):
    """POST: کاربر لاگین‌شده خودش رو از گروه خارج می‌کنه."""
    permission_classes = [IsAuthenticated, IsConversationParticipant]

    def post(self, request, conversation_id):
        leave_conversation(conversation_id=conversation_id, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)