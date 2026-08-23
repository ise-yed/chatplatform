
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.chat.choices import ConversationType, ParticipantRole
from apps.chat.models import Conversation, Participant


def get_existing_direct_conversation(*, user_a, user_b):
    """
    Returns the existing 1:1 (DIRECT) conversation shared by both users,
    or None. The two chained .filter() calls join Participant twice, so
    the match requires the same conversation to contain BOTH users.
    """
    return (
        Conversation.objects.filter(type=ConversationType.DIRECT, participants__user=user_a)
        .filter(participants__user=user_b)
        .first()
    )


@transaction.atomic
def create_direct_conversation(*, creator, other_user):
    """
    یه گفتگوی دو نفره‌ی جدید بین creator و other_user می‌سازه و هر دو
    رو به‌عنوان Participant اضافه می‌کنه.

    قبل از ساخت، دو تا invariant دامنه چک می‌شن:
      - نمی‌شه با خودِ کاربر گفتگو ساخت (creator == other_user). بدون
        این چک، bulk_create دو تا Participant با همون (conversation, user)
        می‌سازه و به unique_conversation_participant می‌خوره و با
        IntegrityError (خطای 500) می‌ترکه.
      - اگه از قبل یه direct conversation بین این دو نفر باشه، همون
        برگردونده می‌شه تا چند تا گفتگوی تکراری برای یه جفت کاربر ساخته
        نشه (data integrity).

    @transaction.atomic اجباریه: این تابع دو تا نوشتن جدا به دیتابیس
    داره (ساخت Conversation، بعد ساخت دو تا Participant). اگه بین این
    دو مرحله خطایی پیش بیاد (مثلاً قطعی connection)، بدون atomic ممکنه
    Conversation بدون هیچ Participant ای باقی بمونه — یعنی یه گفتگوی
    "یتیم" که هیچ‌کس (حتی سازنده‌ش) بهش دسترسی نداره. با atomic، یا
    هر دو مرحله کامل انجام می‌شن یا هیچ‌کدوم (rollback خودکار).

    نکته درباره race: دو تا request همزمان می‌تونن هر دو existing رو
    None ببینن و دو تا گفتگو بسازن. بستنِ کاملِ این حفره به یه
    unique constraint سطح دیتابیس روی جفت کاربر (مثلاً یه فیلد
    مرتب‌شده‌ی pair_key) نیاز داره که migration جدا می‌خواد؛ این چک
    حالت رایج (کلیک دوباره‌ی کاربر) رو می‌گیره.
    """
    if other_user is not None and creator.pk == other_user.pk:
        raise ValidationError('Cannot start a conversation with yourself.')

    existing = get_existing_direct_conversation(user_a=creator, user_b=other_user)
    if existing is not None:
        return existing

    conversation = Conversation.objects.create(type=ConversationType.DIRECT)
    Participant.objects.bulk_create([
        Participant(conversation=conversation, user=creator, role=ParticipantRole.MEMBER),
        Participant(conversation=conversation, user=other_user, role=ParticipantRole.MEMBER),
    ])
    return conversation

