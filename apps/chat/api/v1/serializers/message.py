from rest_framework import serializers

from apps.chat.choices import MessageType
from apps.chat.models import Message
from apps.common.constants import MAX_MESSAGE_LENGTH


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_username', 'type',
            'content', 'attachment', 'attachment_url', 'file_name',
            'file_size', 'mime_type', 'is_edited', 'created_at',
        ]
        read_only_fields = [
            'sender', 'attachment_url', 'file_name', 'file_size', 'mime_type', 'is_edited'
        ]

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url


class SendMessageSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=MessageType.choices, default=MessageType.TEXT)
    content = serializers.CharField(
        max_length=MAX_MESSAGE_LENGTH, required=False, allow_blank=True
    )
    attachment = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        message_type = attrs.get('type', MessageType.TEXT)
        content = attrs.get('content', '')
        attachment = attrs.get('attachment')

        if message_type == MessageType.TEXT and attachment:
            raise serializers.ValidationError(
                {'attachment': 'Text messages cannot contain an attachment.'}
            )

        if message_type != MessageType.TEXT and not attachment:
            raise serializers.ValidationError(
                {'attachment': 'An attachment is required for this message type.'}
            )

        if message_type != MessageType.TEXT and content.strip():
            raise serializers.ValidationError(
                {'content': 'File messages cannot contain text content.'}
            )

        return attrs
