from apps.chat.models import Message


def get_messages_for_conversation(*, conversation_id):
  
    return (
        Message.objects.filter(conversation_id=conversation_id, is_deleted=False)
        .select_related('sender')
        .order_by('created_at')
    )