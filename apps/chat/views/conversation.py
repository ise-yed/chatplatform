from django.contrib.auth.decorators import login_required
from django.shortcuts import render


from apps.chat.selectors import attach_other_participant, get_conversations_for_user


@login_required
def conversation_list_view(request):
    conversations = attach_other_participant(
        conversations=get_conversations_for_user(user=request.user), user=request.user
    )
    return render(request, 'chat/conversation_list.html', {'conversations': conversations})