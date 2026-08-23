from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.chat.services.realtime import broadcast_new_message
from apps.common.constants import MAX_MESSAGE_LENGTH


def send_message(*, conversation_id, sender, content):
    """
    Creates a message and broadcasts it in real time to every consumer
    subscribed to the conversation's group. This is the single place
    where "a message was sent" is handled — called identically from
    the web view (session auth) and the mobile DRF API (JWT auth), so
    every entry point gets the same validation, the same DB write AND
    the same real-time broadcast, with no duplicated logic and no risk
    of a future caller (an import script, an admin action, ...)
    forgetting one of them.

    Content validation lives here (not in a serializer or a view) so
    the domain rules — non-empty, within MAX_MESSAGE_LENGTH — hold no
    matter which transport called us. Raises django.core.exceptions.
    ValidationError, which the DRF exception handler turns into a 400
    and the web view translates into an HttpResponseBadRequest.

    The broadcast is deferred to transaction.on_commit so clients are
    only ever told about a message that actually landed in the
    database. If the surrounding transaction rolls back, the broadcast
    never fires; outside a transaction (autocommit) on_commit runs
    immediately, so the ordering "DB write -> commit -> broadcast" is
    guaranteed either way.
    """
    content = (content or '').strip()
    if not content:
        raise ValidationError('Message content cannot be empty.')
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValidationError(
            f'Message content cannot exceed {MAX_MESSAGE_LENGTH} characters.'
        )

    with transaction.atomic():
        message = Message.objects.create(
            conversation_id=conversation_id, sender=sender, content=content
        )
        # Bump the conversation's activity timestamp so the conversation
        # list (ordered by -updated_at) surfaces newest activity first.
        # .update() is used deliberately: it writes updated_at without
        # loading the row and without re-triggering auto_now.
        Conversation.objects.filter(id=conversation_id).update(updated_at=timezone.now())
        transaction.on_commit(lambda: broadcast_new_message(message=message))

    return message
