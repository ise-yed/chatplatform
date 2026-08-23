from apps.chat.models import Message, Participant
from apps.chat.services.realtime import broadcast_read_receipt


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