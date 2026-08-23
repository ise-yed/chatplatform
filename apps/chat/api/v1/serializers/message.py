from rest_framework import serializers

from apps.chat.models import Message
from apps.common.constants import MAX_MESSAGE_LENGTH


class MessageSerializer(serializers.ModelSerializer):
    """
    شکل خروجی یه پیام — شامل username فرستنده برای نمایش مستقیم در UI
    بدون نیاز کلاینت به یه request جدا برای گرفتن اطلاعات فرستنده.
    """
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'sender_username', 'type', 'content', 'is_edited', 'created_at']
        read_only_fields = ['sender', 'is_edited']


class SendMessageSerializer(serializers.Serializer):
    """
    شکل ورودی برای فرستادن پیام جدید — فقط content.

    sender و conversation عمداً اینجا نیستن: sender از request.user
    میاد، conversation از URL. اگه این‌ها رو تو body قابل ارسال می‌ذاشتیم،
    کاربر می‌تونست جعل هویت کنه (مثلاً پیامی رو به اسم یوزر دیگه بفرسته)
    یا پیام رو تو یه گفتگوی دیگه تزریق کنه.
    """
    content = serializers.CharField(max_length=MAX_MESSAGE_LENGTH)