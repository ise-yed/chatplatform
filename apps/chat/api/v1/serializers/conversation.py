from rest_framework import serializers

from apps.chat.models import Conversation
from apps.chat.api.v1.serializers.message import MessageSerializer

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
    last_message = serializers.SerializerMethodField() 


    class Meta:
        model = Conversation
        fields = ['id', 'type', 'title', 'is_archived', 'participants', 'created_at', 'updated_at' ,'last_message' ]

    def get_participants(self, obj):
        """
        چون Participant یه جدول واسط با متادیتاست (نه مستقیم User)،
        نمی‌شه از رابطه‌ی ModelSerializer پیش‌فرض استفاده کرد — باید
        صریح از هر Participant، فیلد user رو استخراج کنیم.
        """
        return ParticipantUserSerializer(
            [p.user for p in obj.participants.all()], many=True
        ).data
        
    def get_last_message(self, obj):
        """
        آخرین پیام گفتگو رو با استفاده از MessageSerializer سریالایز می‌کنه.
        اگر last_message نال باشه، None برمی‌گردونه.
        """
        if obj.last_message:
            return MessageSerializer(obj.last_message, context=self.context).data
        return None

class CreateDirectConversationSerializer(serializers.Serializer):
    """
    شکل ورودی برای ساخت گفتگوی جدید — فقط id کاربر مقابل لازمه؛
    creator از request.user گرفته می‌شه، نه از body (تا کاربر نتونه
    به‌جای خودش یه یوزر دیگه رو به‌عنوان سازنده جا بزنه).
    """
    other_user_id = serializers.UUIDField()
    
    

class CreateGroupConversationSerializer(serializers.Serializer):
    """
    ورودی ساخت گروه. participant_ids اختیاریه — یه گروه می‌تونه فقط
    با سازنده ساخته بشه و بعداً از طریق endpoint اضافه‌کردن عضو رشد کنه.
    """
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    avatar = serializers.ImageField(required=False, allow_null=True)
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True, default=list
    )


class AddParticipantSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()


class GroupParticipantSerializer(serializers.Serializer):
    """
    یه عضو گروه به همراه نقشش — برای این‌که UI بتونه بج «ادمین» رو نشون بده.
    """
    id = serializers.UUIDField(source='user.id')
    username = serializers.CharField(source='user.username')
    role = serializers.CharField()