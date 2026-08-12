import pytest

from apps.chat.choices import ConversationType, ParticipantRole
from apps.chat.models import Conversation, Message, Participant
from apps.chat.services import create_direct_conversation, send_message

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