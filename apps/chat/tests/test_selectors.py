import pytest
from apps.chat.selectors import (
    get_conversation_for_user,
    get_conversations_for_user,
    get_messages_for_conversation,
    is_user_participant,
    get_group_participants, 
    is_conversation_admin,
    get_latest_other_participant_read_message
)
from apps.chat.services import create_direct_conversation, send_message,create_group_conversation ,mark_conversation_as_read

pytestmark = pytest.mark.django_db


def test_is_user_participant_returns_true_for_member(user_a, user_b):
    """A user who is a Participant of the conversation should return True."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    assert is_user_participant(conversation_id=conversation.id, user=user_a) is True


def test_is_user_participant_returns_false_for_non_member(user_a, user_b, outsider):
    """A user who is NOT a Participant of the conversation should return False."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    assert is_user_participant(conversation_id=conversation.id, user=outsider) is False


def test_get_conversations_for_user_includes_own_conversation(user_a, user_b):
    """A user's conversation list must include conversations they participate in."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    conversations = get_conversations_for_user(user=user_a)
    assert conversation in conversations


def test_get_conversations_for_user_excludes_others_conversations(user_a, user_b, outsider):
    """A user's conversation list must NOT include conversations they are not part of."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    conversations = get_conversations_for_user(user=outsider)
    assert conversation not in conversations


def test_get_conversation_for_user_returns_conversation_for_member(user_a, user_b):
    """A member should get the conversation back by id."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    result = get_conversation_for_user(conversation_id=conversation.id, user=user_a)
    assert result == conversation


def test_get_conversation_for_user_returns_none_for_non_member(user_a, user_b, outsider):
    """A non-member should get None, not the conversation."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    result = get_conversation_for_user(conversation_id=conversation.id, user=outsider)
    assert result is None


def test_get_messages_for_conversation_returns_chronological_order(user_a, user_b):
    """Messages must come back ordered oldest-first (matches Meta.ordering)."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    first = send_message(conversation_id=conversation.id, sender=user_a, content='first')
    second = send_message(conversation_id=conversation.id, sender=user_a, content='second')

    messages = list(get_messages_for_conversation(conversation_id=conversation.id))
    assert messages == [first, second]


def test_get_messages_for_conversation_excludes_soft_deleted(user_a, user_b):
    """A message with is_deleted=True must not appear in the results."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='to delete')
    message.is_deleted = True
    message.save(update_fields=['is_deleted'])

    messages = get_messages_for_conversation(conversation_id=conversation.id)
    assert message not in messages
    
    

def test_get_other_participant_last_read_message_returns_none_initially(user_a, user_b):
    """Before anyone reads anything, this must be None."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    result = get_latest_other_participant_read_message(conversation_id=conversation.id, user=user_a)
    assert result is None


def test_get_other_participant_last_read_message_reflects_the_other_users_read(user_a, user_b):
    """After user_b reads, user_a's view of 'other's last read' must show it."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    message = send_message(conversation_id=conversation.id, sender=user_a, content='hi')
    mark_conversation_as_read(conversation_id=conversation.id, user=user_b)

    result = get_latest_other_participant_read_message(conversation_id=conversation.id, user=user_a)
    assert result == message
    



def test_is_conversation_admin_true_for_admin(user_a):
    conversation = create_group_conversation(creator=user_a, title='Team')
    assert is_conversation_admin(conversation_id=conversation.id, user=user_a) is True


def test_is_conversation_admin_false_for_member(user_a, user_b):
    conversation = create_group_conversation(creator=user_a, title='Team', participant_ids=[user_b.id])
    assert is_conversation_admin(conversation_id=conversation.id, user=user_b) is False


def test_get_group_participants_returns_all_members(user_a, user_b):
    conversation = create_group_conversation(creator=user_a, title='Team', participant_ids=[user_b.id])
    user_ids = {p.user_id for p in get_group_participants(conversation_id=conversation.id)}
    assert user_ids == {user_a.id, user_b.id}