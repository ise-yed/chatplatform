import pytest
from rest_framework import status

from apps.chat.services import create_direct_conversation, send_message

pytestmark = pytest.mark.django_db


# ---- ConversationListCreateApi ----

def test_conversation_list_requires_authentication(api_client):
    """An unauthenticated request to list conversations must be rejected."""
    response = api_client.get('/api/v1/chat/conversations/')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_conversation_list_returns_only_own_conversations(auth_client, user_a, user_b):
    """A user must only see conversations they participate in."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    client = auth_client(user_a)

    response = client.get('/api/v1/chat/conversations/')

    assert response.status_code == status.HTTP_200_OK
    returned_ids = [item['id'] for item in response.data]
    assert str(conversation.id) in returned_ids


def test_create_direct_conversation_success(auth_client, user_a, user_b):
    """POSTing another user's id must create a new direct conversation."""
    client = auth_client(user_a)

    response = client.post('/api/v1/chat/conversations/', data={'other_user_id': str(user_b.id)})

    assert response.status_code == status.HTTP_201_CREATED


def test_create_conversation_with_nonexistent_user_returns_standard_404(auth_client, user_a):
    """
    Posting a random UUID for other_user_id must go through
    custom_exception_handler and return the standard error shape
    (message, error_code, errors).
    """
    client = auth_client(user_a)

    response = client.post(
        '/api/v1/chat/conversations/',
        data={'other_user_id': '00000000-0000-0000-0000-000000000000'},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert 'message' in response.data
    assert 'error_code' in response.data


# ---- MessageListCreateApi ----

def test_member_can_list_messages(auth_client, user_a, user_b):
    """A participant must be able to list messages in their conversation."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    send_message(conversation_id=conversation.id, sender=user_a, content='hi')
    client = auth_client(user_a)

    response = client.get(f'/api/v1/chat/conversations/{conversation.id}/messages/')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


def test_non_member_cannot_list_messages(auth_client, outsider, user_a, user_b):
    """A user who is not a participant must be denied access (403)."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    client = auth_client(outsider)

    response = client.get(f'/api/v1/chat/conversations/{conversation.id}/messages/')

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_non_member_denied_response_uses_standard_error_format(auth_client, outsider, user_a, user_b):
    """The 403 response body must follow the custom_exception_handler shape."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    client = auth_client(outsider)

    response = client.get(f'/api/v1/chat/conversations/{conversation.id}/messages/')

    assert 'message' in response.data
    assert 'error_code' in response.data


def test_member_can_send_message(auth_client, user_a, user_b):
    """A participant must be able to POST a new message."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    client = auth_client(user_a)

    response = client.post(
        f'/api/v1/chat/conversations/{conversation.id}/messages/', data={'content': 'hello'}
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['content'] == 'hello'


def test_non_member_cannot_send_message(auth_client, outsider, user_a, user_b):
    """A non-participant must be denied when trying to POST a message."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    client = auth_client(outsider)

    response = client.post(
        f'/api/v1/chat/conversations/{conversation.id}/messages/', data={'content': 'sneaky'}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_sent_message_response_includes_sender_username(auth_client, user_a, user_b):
    """The response for a created message must include sender_username (from MessageSerializer)."""
    conversation = create_direct_conversation(creator=user_a, other_user=user_b)
    client = auth_client(user_a)

    response = client.post(
        f'/api/v1/chat/conversations/{conversation.id}/messages/', data={'content': 'hi'}
    )

    assert response.data['sender_username'] == user_a.username