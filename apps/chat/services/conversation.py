
from django.db import transaction

from apps.chat.choices import ConversationType, ParticipantRole
from apps.chat.models import Conversation, Participant


@transaction.atomic
def create_direct_conversation(*, creator, other_user):
    """
    یه گفتگوی دو نفره‌ی جدید بین creator و other_user می‌سازه و هر دو
    رو به‌عنوان Participant اضافه می‌کنه.

    @transaction.atomic اجباریه: این تابع دو تا نوشتن جدا به دیتابیس
    داره (ساخت Conversation، بعد ساخت دو تا Participant). اگه بین این
    دو مرحله خطایی پیش بیاد (مثلاً قطعی connection)، بدون atomic ممکنه
    Conversation بدون هیچ Participant ای باقی بمونه — یعنی یه گفتگوی
    "یتیم" که هیچ‌کس (حتی سازنده‌ش) بهش دسترسی نداره. با atomic، یا
    هر دو مرحله کامل انجام می‌شن یا هیچ‌کدوم (rollback خودکار).
    """
    conversation = Conversation.objects.create(type=ConversationType.DIRECT)
    Participant.objects.bulk_create([
        Participant(conversation=conversation, user=creator, role=ParticipantRole.MEMBER),
        Participant(conversation=conversation, user=other_user, role=ParticipantRole.MEMBER),
    ])
    return conversation

