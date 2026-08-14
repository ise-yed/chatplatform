from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from apps.chat.selectors import (
    get_conversation_for_user,
    get_messages_for_conversation,
    get_other_participant_last_read_message,

    is_user_participant,
)
from apps.chat.services import send_message


@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_conversation_for_user(conversation_id=conversation_id, user=request.user)
    if conversation is None:
        return HttpResponseForbidden('You are not a participant of this conversation.')

    messages = get_messages_for_conversation(conversation_id=conversation_id)
    other_last_read_message = get_other_participant_last_read_message(
        conversation_id=conversation_id, user=request.user
    )
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
def send_message_view(request, conversation_id):
    """
    Handles the HTMX POST for sending a new message. Returns only the
    HTML fragment for the newly created message (not a full page) —
    HTMX swaps this fragment into the message list on the client side
    without a full page reload.
    """
    if not is_user_participant(conversation_id=conversation_id, user=request.user):
        return HttpResponseForbidden('You are not a participant of this conversation.')

    content = request.POST.get('content', '').strip()
    if not content:
        return HttpResponseForbidden('Message content cannot be empty.')

    message = send_message(conversation_id=conversation_id, sender=request.user, content=content)

    return HttpResponse(status=204)
    # return render(request, 'chat/partials/message_item.html', {'message': message})