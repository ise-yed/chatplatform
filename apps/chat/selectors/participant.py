from apps.chat.models import Participant


def is_user_participant(*, conversation_id, user):
    return Participant.objects.filter(conversation_id=conversation_id, user=user).exists()