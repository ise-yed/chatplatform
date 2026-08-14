from apps.chat.models import Conversation


def get_conversations_for_user(*, user):
 
    return (
        Conversation.objects.filter(participants__user=user)
        .distinct()
        .prefetch_related('participants__user')
    )
    
def get_conversation_for_user(*, conversation_id, user):
    
    return Conversation.objects.filter(
        id=conversation_id, participants__user=user
    ).first()