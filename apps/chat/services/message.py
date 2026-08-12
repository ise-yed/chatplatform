from apps.chat.models import Message


def send_message(*, conversation_id, sender, content):
    message = Message.objects.create(
        conversation_id=conversation_id, sender=sender, content=content
    )
    return message