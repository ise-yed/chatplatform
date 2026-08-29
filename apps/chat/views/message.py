from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.chat.selectors import (
    attach_other_participant,
    get_conversation_for_user,
    get_latest_other_participant_read_message,
    get_messages_for_conversation,
    is_user_participant,
)
from apps.chat.services import send_message


@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_conversation_for_user(conversation_id=conversation_id, user=request.user)
    if conversation is None:
        return HttpResponseForbidden('You are not a participant of this conversation.')

    messages = get_messages_for_conversation(conversation_id=conversation_id)
    other_last_read_message = get_latest_other_participant_read_message(
        conversation_id=conversation_id, user=request.user
    )
    conversation = attach_other_participant(conversations=[conversation], user=request.user)[0]
    return render(
        request,
        'chat/conversation_detail.html',
        {
            'conversation': conversation,
            'messages': messages,
            'other_last_read_message': other_last_read_message,
        },
    )
    

@login_required
@require_POST
def send_message_view(request, conversation_id):
    """
    Sends a new message to a conversation from the web client.

    POST-only: sending a message changes state, so a GET (or any other
    method) is rejected with 405 by @require_POST. Content validation
    (non-empty, max length) is delegated to the send_message service so
    the web path and the mobile API path enforce identical domain rules;
    a ValidationError from the service becomes a 400 here.

    Returns 204 No Content on success — the new message reaches the
    client over the WebSocket broadcast, so there's no body to return.
    """
    if not is_user_participant(conversation_id=conversation_id, user=request.user):
        return HttpResponseForbidden('You are not a participant of this conversation.')

    try:
        send_message(
            conversation_id=conversation_id,
            sender=request.user,
            message_type=request.POST.get('type', 'text'),
            content=request.POST.get('content', ''),
            attachment=request.FILES.get('attachment'),
        )
    except ValidationError as exc:
        return HttpResponseBadRequest(' '.join(exc.messages))

    return HttpResponse(status=204)