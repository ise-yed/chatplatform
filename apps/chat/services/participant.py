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
    Does nothing if the conversation has no messages yet, or if the
    given user isn't actually a participant (the .update() call
    simply matches zero rows).
    """
    if message_id is None:
        message = Message.objects.filter(conversation_id=conversation_id).order_by('-created_at').first()
    else:
        message = Message.objects.filter(id=message_id, conversation_id=conversation_id).first()

    if message is None:
        return

    updated = Participant.objects.filter(
        conversation_id=conversation_id, user=user
    ).update(last_read_message=message)

    if updated:
        broadcast_read_receipt(
            conversation_id=conversation_id, user_id=user.id, last_read_message_id=message.id
        )