from apps.chat.models import Participant


def is_user_participant(*, conversation_id, user):
    return Participant.objects.filter(conversation_id=conversation_id, user=user).exists()


def get_other_participant_last_read_message(*, conversation_id, user):
    """
    Returns the Message the OTHER participant (not the given user) has
    last read in this conversation, or None if they haven't read
    anything yet. Used to decide whether the current user's own sent
    messages should render as "seen" on initial page load.

    Assumes a direct (2-person) conversation — group conversations
    will need a per-message, per-participant read model later (Phase 8).
    """
    participant = (
        Participant.objects.filter(conversation_id=conversation_id)
        .exclude(user=user)
        .select_related('last_read_message')
        .first()
    )
    return participant.last_read_message if participant else None