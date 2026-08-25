import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.chat.services import mark_conversation_as_read, send_message

from datetime import timedelta

from django.core.exceptions import ValidationError

from apps.chat.choices import ConversationType, ParticipantRole
from apps.chat.models import Conversation, Message, Participant
from apps.chat.services import create_direct_conversation, send_message
from apps.common.constants import MAX_MESSAGE_LENGTH

pytestmark = pytest.mark.django_db


def test_creates_conversation_with_direct_type(user_a, user_b):
    """The created conversation should have type=DIRECT."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    assert conversation.type == ConversationType.DIRECT


def test_adds_both_users_as_participants(user_a, user_b):
    """Both the creator and the other user must become Participants."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    participant_user_ids = set(
        Participant.objects.filter(conversation=conversation).values_list('user_id', flat=True)
    )
    assert participant_user_ids == {user_a.id, user_b.id}


def test_participants_have_member_role(user_a, user_b):
    """Both participants should default to the MEMBER role."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    roles = set(Participant.objects.filter(conversation=conversation).values_list('role', flat=True))
    assert roles == {ParticipantRole.MEMBER}


def test_is_atomic_no_orphan_conversation_on_failure(user_a):
    """
    If Participant creation fails (e.g. other_user is None), the
    Conversation must not be left behind — transaction.atomic should
    roll back both writes together.
    """
    with pytest.raises(Exception):
        create_direct_conversation(creator=user_a, other_user=None)
    assert Conversation.objects.count() == 0


def test_send_message_creates_message_with_correct_content(user_a, user_b):
    """The saved message's content must match what was passed in."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='hello')
    assert message.content == 'hello'


def test_send_message_links_correct_conversation_and_sender(user_a, user_b):
    """The message must reference the given conversation and sender."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='hi')
    assert message.conversation_id == conversation.id
    assert message.sender_id == user_a.id


def test_send_message_is_persisted_to_database(user_a, user_b):
    """The message must actually exist in the database after the call."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='saved?')
    assert Message.objects.filter(id=message.id).exists()
    
    
def test_mark_conversation_as_read_updates_participant(user_a, user_b):
    """The reading user's Participant.last_read_message must be updated."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='hi')

    mark_conversation_as_read(conversation_id=conversation.id, user=user_b)

    participant = Participant.objects.get(conversation=conversation, user=user_b)
    assert participant.last_read_message_id == message.id


def test_mark_conversation_as_read_with_no_messages_does_nothing(user_a, user_b):
    """Marking an empty conversation as read must not raise or update anything."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    mark_conversation_as_read(conversation_id=conversation.id, user=user_b)

    participant = Participant.objects.get(conversation=conversation, user=user_b)
    assert participant.last_read_message_id is None


def test_mark_conversation_as_read_does_not_move_backward(user_a, user_b):
    """
    A stale/out-of-order 'seen' for an OLDER message must not drag the
    read pointer backward once it has advanced (monotonic invariant).
    """
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    older = send_message(conversation_id=conversation.id, sender=user_a, content='older')
    newer = send_message(conversation_id=conversation.id, sender=user_a, content='newer')
    # Make ordering deterministic regardless of clock resolution.
    Message.objects.filter(id=older.id).update(created_at=newer.created_at - timedelta(minutes=1))

    mark_conversation_as_read(conversation_id=conversation.id, user=user_b, message_id=newer.id)
    mark_conversation_as_read(conversation_id=conversation.id, user=user_b, message_id=older.id)

    participant = Participant.objects.get(conversation=conversation, user=user_b)
    assert participant.last_read_message_id == newer.id


def test_mark_conversation_as_read_advances_forward(user_a, user_b):
    """The pointer must still advance when a newer message is acked."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    older = send_message(conversation_id=conversation.id, sender=user_a, content='older')
    newer = send_message(conversation_id=conversation.id, sender=user_a, content='newer')
    Message.objects.filter(id=older.id).update(created_at=newer.created_at - timedelta(minutes=1))

    mark_conversation_as_read(conversation_id=conversation.id, user=user_b, message_id=older.id)
    mark_conversation_as_read(conversation_id=conversation.id, user=user_b, message_id=newer.id)

    participant = Participant.objects.get(conversation=conversation, user=user_b)
    assert participant.last_read_message_id == newer.id


# ---- create_direct_conversation invariants ----

def test_cannot_create_direct_conversation_with_self(user_a):
    """Starting a conversation with yourself must raise, not 500 on IntegrityError."""
    with pytest.raises(ValidationError):
        create_direct_conversation(creator=user_a, other_user=user_a)
    assert Conversation.objects.count() == 0


def test_direct_conversation_is_not_duplicated_for_same_pair(user_a, user_b):
    """A second create for the same pair must return the existing conversation."""
    first = create_direct_conversation(creator=user_a, other_user=user_b)
    second = create_direct_conversation(creator=user_b, other_user=user_a)

    assert first.id == second.id
    assert Conversation.objects.filter(type=ConversationType.DIRECT).count() == 1


# ---- send_message validation (shared domain rules) ----

def test_send_message_rejects_empty_content(user_a, user_b):
    """Empty / whitespace-only content must be rejected regardless of transport."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    with pytest.raises(ValidationError):
        send_message(conversation_id=conversation.id, sender=user_a, content='   ')
    assert Message.objects.filter(conversation=conversation).count() == 0


def test_send_message_rejects_content_over_max_length(user_a, user_b):
    """Content longer than MAX_MESSAGE_LENGTH must be rejected (web can't bypass the API cap)."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    with pytest.raises(ValidationError):
        send_message(
            conversation_id=conversation.id, sender=user_a, content='x' * (MAX_MESSAGE_LENGTH + 1)
        )
    assert Message.objects.filter(conversation=conversation).count() == 0


def test_send_message_strips_surrounding_whitespace(user_a, user_b):
    """Leading/trailing whitespace is trimmed before persisting."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='  hi  ')
    assert message.content == 'hi'

def test_send_image_message_saves_attachment(user_a, user_b):
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    image = SimpleUploadedFile('photo.jpg', b'fake-image', content_type='image/jpeg')

    message = send_message(
        conversation_id=conversation.id,
        sender=user_a,
        message_type='image',
        attachment=image,
    )

    assert message.type == 'image'
    assert message.attachment
    assert message.file_name == 'photo.jpg'
    assert message.mime_type == 'image/jpeg'
    assert message.file_size == len(b'fake-image')


def test_send_music_message_rejects_non_audio(user_a, user_b):
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    image = SimpleUploadedFile('photo.jpg', b'fake-image', content_type='image/jpeg')

    with pytest.raises(ValidationError):
        send_message(
            conversation_id=conversation.id,
            sender=user_a,
            message_type='music',
            attachment=image,
        )


def test_send_text_message_rejects_attachment(user_a, user_b):
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    file = SimpleUploadedFile('note.txt', b'hello', content_type='text/plain')

    with pytest.raises(ValidationError):
        send_message(
            conversation_id=conversation.id,
            sender=user_a,
            message_type='text',
            attachment=file,
        )
