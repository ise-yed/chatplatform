
from django.core.exceptions import  ValidationError
from django.db import transaction

from apps.chat.choices import ConversationType, ConversationUpdateAction, ParticipantRole
from apps.chat.models import Conversation, Participant
from apps.chat.services.realtime import broadcast_conversation_update
from apps.common.constants import MAX_GROUP_PARTICIPANTS


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
    
    transaction.on_commit(
        lambda: broadcast_conversation_update(
            conversation=conversation,
            action=ConversationUpdateAction.conversation_added, 
            participant_ids=[other_user.id],
            last_message=None,
        )
    )

    return conversation


@transaction.atomic
def create_group_conversation(*, creator, title, description='', avatar=None, participant_ids=None):
    """
    Creates a new GROUP conversation. `creator` automatically becomes
    an ADMIN participant; every id in `participant_ids` is added as a
    MEMBER. `creator`'s own id is silently dropped from
    `participant_ids` if present, so callers don't have to worry
    about the caller accidentally double-adding themselves.

    Existence/validity of the ids in `participant_ids` is NOT this
    function's job — the caller (API view/serializer) is expected to
    have already resolved them to real User instances/ids, the same
    way create_direct_conversation's caller resolves other_user_id
    before calling in.

    @transaction.atomic for the same reason as create_direct_conversation:
    Conversation and its Participant rows are two separate writes: without
    atomicity, a failure between them (e.g. a duplicate id causing an
    IntegrityError on bulk_create) could leave an orphaned Conversation
    with no participants at all.
    """
    title = (title or '').strip()
    if not title:
        raise ValidationError('Group title is required.')

    participant_ids = set(participant_ids or [])
    participant_ids.discard(creator.pk)

    total_members = len(participant_ids) + 1  # +1 for the creator
    if total_members > MAX_GROUP_PARTICIPANTS:
        raise ValidationError(f'A group cannot have more than {MAX_GROUP_PARTICIPANTS} members.')

    conversation = Conversation.objects.create(
        type=ConversationType.GROUP,
        title=title,
        description=(description or '').strip(),
        avatar=avatar,
    )

    participants = [Participant(conversation=conversation, user_id=creator.pk, role=ParticipantRole.ADMIN)]
    participants += [
        Participant(conversation=conversation, user_id=user_id, role=ParticipantRole.MEMBER)
        for user_id in participant_ids
    ]
    
    Participant.objects.bulk_create(participants)
    all_participant_ids = list(participant_ids) 
    if all_participant_ids:
        transaction.on_commit(
            lambda: broadcast_conversation_update(
                conversation=conversation,
                action=ConversationUpdateAction.conversation_added,
                participant_ids=all_participant_ids,
                last_message=None,
                extra_data={'user_id': str(creator.id), 'username': creator.username},
            )
        )
    return conversation






@transaction.atomic
def leave_conversation(*, conversation_id, user):
    """
    A participant removes themselves from a GROUP conversation. Any
    member (not just admins) can leave. Same last-admin guard as
    remove_participant — an admin who is the only admin must promote
    someone else first (role-change service comes in a later phase).
    """
    participant = Participant.objects.filter(conversation_id=conversation_id, user=user).first()
    if participant is None:
        raise ValidationError('You are not a participant of this conversation.')

    if participant.role == ParticipantRole.ADMIN:
        remaining_admins = Participant.objects.filter(
            conversation_id=conversation_id, role=ParticipantRole.ADMIN
        ).exclude(id=participant.id).count()
        if remaining_admins == 0:
            raise ValidationError(
                'You are the only admin of this group. Promote another member before leaving.'
            )

    participant.delete()