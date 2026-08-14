from apps.chat.models import Message
from apps.chat.services.realtime import broadcast_new_message


def send_message(*, conversation_id, sender, content):
    """
    Creates a message and broadcasts it in real time to every consumer
    subscribed to the conversation's group. This is the single place
    where "a message was sent" is handled — called identically from
    the web view (session auth) and the mobile DRF API (JWT auth), so
    every entry point gets the same DB write AND the same real-time
    broadcast, with no duplicated logic and no risk of a future caller
    (an import script, an admin action, ...) forgetting to broadcast.
    """
    message = Message.objects.create(
        conversation_id=conversation_id, sender=sender, content=content
    )
    broadcast_new_message(message=message)
    return message