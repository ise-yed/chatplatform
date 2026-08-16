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
    
    
def attach_other_participant(*, conversations, user):
    """
    Given conversations already prefetched with participants__user,
    attaches an `other_participant` attribute to each one (the User
    on the other side of a direct conversation). This is template-only
    convenience data, not persisted — it exists so conversation_list.html
    can show who each conversation is with, plus their online status.

    Assumes 2-person (direct) conversations — group conversations will
    need different rendering entirely (Phase 8).
    """
    for conversation in conversations:
        conversation.other_participant = next(
            (p.user for p in conversation.participants.all() if p.user_id != user.id), None
        )
    return conversations