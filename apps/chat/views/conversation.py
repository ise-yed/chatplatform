from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.chat.selectors import get_conversations_for_user


@login_required
def conversation_list_view(request):
    """
    Renders the full inbox page — the list of conversations the
    logged-in user participates in. This is a normal full-page view,
    not an HTMX partial, since it's the page the browser navigates to.
    """
    conversations = get_conversations_for_user(user=request.user)
    return render(request, 'chat/conversation_list.html', {'conversations': conversations})