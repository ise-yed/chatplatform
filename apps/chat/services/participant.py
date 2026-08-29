from django.db import transaction

from apps.chat.models import Message, Participant ,Conversation
from apps.chat.services.realtime import broadcast_read_receipt
from django.core.exceptions import PermissionDenied, ValidationError
from apps.chat.choices import ConversationType, ParticipantRole
from apps.common.constants import MAX_GROUP_PARTICIPANTS

def mark_conversation_as_read(*, conversation_id, user, message_id=None):
    """
    Moves this user's Participant.last_read_message pointer forward to
    the given message — or to whatever the latest message in the
    conversation currently is, if message_id isn't given (used when a
    user opens or reconnects to a conversation).

    Broadcasts a read receipt afterward so other participants'
    clients can update their own "seen" indicators in real time.
    Does nothing if the conversation has no messages yet, if the given
    user isn't actually a participant, or if the pointer would move
    backward (see the monotonic guard below).
    """
    if message_id is None:
        message = Message.objects.filter(conversation_id=conversation_id).order_by('-created_at').first()
    else:
        message = Message.objects.filter(id=message_id, conversation_id=conversation_id).first()

    if message is None:
        return

    participant = (
        Participant.objects.filter(conversation_id=conversation_id, user=user)
        .select_related('last_read_message')
        .first()
    )
    if participant is None:
        return

    # Monotonic: the read pointer only ever moves forward. A stale or
    # out-of-order "seen" (e.g. a client acking an older message, or a
    # reconnect replaying an old id) must not drag it backward — that
    # would wrongly resurrect already-seen messages as unread and flip
    # the sender's "seen" checkmarks back off.
    current = participant.last_read_message
    if current is not None and message.created_at <= current.created_at:
        return

    participant.last_read_message = message
    participant.save(update_fields=['last_read_message', 'updated_at'])

    broadcast_read_receipt(
        conversation_id=conversation_id, user_id=user.id, last_read_message_id=message.id
    )
    
def _get_admin_participant_or_raise(*, conversation_id, actor):
    """
    Internal helper: returns actor's Participant row if actor is an
    ADMIN of this conversation, otherwise raises PermissionDenied.
    Shared by add_participant and remove_participant so the "must be
    admin" check has exactly one implementation.
    """
    participant = Participant.objects.filter(conversation_id=conversation_id, user=actor).first()
    if participant is None or participant.role != ParticipantRole.ADMIN:
        raise PermissionDenied('Only group admins can manage participants.')
    return participant



@transaction.atomic
def add_participant(*, conversation_id, actor, user):
    """
    Adds `user` to a GROUP conversation as a MEMBER. Only callable by
    an existing ADMIN of that conversation (`actor`) — enforced here,
    not just at the permission-class layer, so this remains true no
    matter where the call comes from.
    """
    conversation = Conversation.objects.filter(id=conversation_id, type=ConversationType.GROUP).first()
    if conversation is None:
        raise ValidationError('Group conversation not found.')

    _get_admin_participant_or_raise(conversation_id=conversation_id, actor=actor)

    if Participant.objects.filter(conversation_id=conversation_id, user=user).exists():
        raise ValidationError('This user is already a participant.')

    current_count = Participant.objects.filter(conversation_id=conversation_id).count()
    if current_count >= MAX_GROUP_PARTICIPANTS:
        raise ValidationError(f'A group cannot have more than {MAX_GROUP_PARTICIPANTS} members.')

    return Participant.objects.create(conversation=conversation, user=user, role=ParticipantRole.MEMBER)


@transaction.atomic
def remove_participant(*, conversation_id, actor, user_id):
    """
    Removes a participant from a GROUP conversation. Admin-only, same
    reasoning as add_participant.

    Refuses to remove an ADMIN if they are the conversation's only
    remaining admin — otherwise the group would end up with no one
    able to manage membership at all.
    """
    _get_admin_participant_or_raise(conversation_id=conversation_id, actor=actor)

    target = Participant.objects.filter(conversation_id=conversation_id, user_id=user_id).first()
    if target is None:
        raise ValidationError('This user is not a participant of this conversation.')

    if target.role == ParticipantRole.ADMIN:
        remaining_admins = Participant.objects.filter(
            conversation_id=conversation_id, role=ParticipantRole.ADMIN
        ).exclude(id=target.id).count()
        if remaining_admins == 0:
            raise ValidationError('Cannot remove the only remaining admin of this group.')

    target.delete()