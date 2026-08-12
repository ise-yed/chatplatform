from rest_framework import serializers

from apps.chat.models import Conversation


class ParticipantUserSerializer(serializers.Serializer):
    """
    نمایش خلاصه‌ی یه کاربر شرکت‌کننده در گفتگو (فقط id و username).

    عمداً همه‌ی فیلدهای User (مثل email) رو برنمی‌گردونه — یه کاربر
    عضو گفتگو نباید بتونه اطلاعات خصوصی بقیه‌ی شرکت‌کننده‌ها رو ببینه،
    فقط چیزی که برای نمایش UI لازمه.
    """
    id = serializers.UUIDField()
    username = serializers.CharField()


class ConversationListSerializer(serializers.ModelSerializer):
    """
    شکل خروجی یه گفتگو برای لیست/جزئیات — شامل لیست شرکت‌کننده‌ها.
    """
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'type', 'title', 'is_archived', 'participants', 'created_at', 'updated_at']

    def get_participants(self, obj):
        """
        چون Participant یه جدول واسط با متادیتاست (نه مستقیم User)،
        نمی‌شه از رابطه‌ی ModelSerializer پیش‌فرض استفاده کرد — باید
        صریح از هر Participant، فیلد user رو استخراج کنیم.
        """
        return ParticipantUserSerializer(
            [p.user for p in obj.participants.all()], many=True
        ).data


class CreateDirectConversationSerializer(serializers.Serializer):
    """
    شکل ورودی برای ساخت گفتگوی جدید — فقط id کاربر مقابل لازمه؛
    creator از request.user گرفته می‌شه، نه از body (تا کاربر نتونه
    به‌جای خودش یه یوزر دیگه رو به‌عنوان سازنده جا بزنه).
    """
    other_user_id = serializers.UUIDField()