/*
|--------------------------------------------------------------------------
| Scroll chat to bottom
|--------------------------------------------------------------------------
*/

function scrollChatToBottom() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    container.scrollTop = container.scrollHeight;
}

/*
|--------------------------------------------------------------------------
| Build a message element (mirrors chat/partials/message_item.html)
|--------------------------------------------------------------------------
| Uses textContent (never innerHTML) for anything that came from the
| server/user — content and username are untrusted data now that
| Django's template auto-escaping isn't involved in rendering them.
*/

function buildMessageElement(message) {
    const isMe = String(message.sender_id) === document.body.dataset.userId;

    const row = document.createElement('div');
    row.className = `message-row ${isMe ? 'message-me' : 'message-other'}`;
    row.dataset.messageId = message.id;

    if (!isMe) {
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = message.sender_username.charAt(0).toUpperCase();
        row.appendChild(avatar);
    }

    const contentWrap = document.createElement('div');
    contentWrap.className = 'message-content';

    if (!isMe) {
        const senderEl = document.createElement('div');
        senderEl.className = 'message-sender';
        senderEl.textContent = message.sender_username;
        contentWrap.appendChild(senderEl);
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const textEl = document.createElement('div');
    textEl.className = 'message-text';
    textEl.textContent = message.content;
    bubble.appendChild(textEl);

    const meta = document.createElement('div');
    meta.className = 'message-meta';

    const timeEl = document.createElement('span');
    timeEl.className = 'message-time';
    timeEl.textContent = new Date(message.created_at).toLocaleTimeString('fa-IR', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
    meta.appendChild(timeEl);

    if (isMe) {
        const statusEl = document.createElement('span');
        statusEl.className = 'message-status';
        statusEl.title = 'ارسال شده';
        statusEl.innerHTML = '<i class="bi bi-check2-all"></i>'; // static markup only, no user data
        meta.appendChild(statusEl);
    }

    bubble.appendChild(meta);
    contentWrap.appendChild(bubble);
    row.appendChild(contentWrap);

    return row;
}

/*
|--------------------------------------------------------------------------
| WebSocket connection + event wiring
|--------------------------------------------------------------------------
*/

document.addEventListener('DOMContentLoaded', function () {
    scrollChatToBottom();

    const chatWindow = document.querySelector('.chat-window');
    if (!chatWindow) return;

    const conversationId = chatWindow.dataset.conversationId;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new ChatSocket(`${protocol}//${window.location.host}/ws/chat/${conversationId}/`);

    socket.on('message.new', function (data) {
        const messageList = document.getElementById('message-list');
        if (!messageList) return;

        const emptyState = messageList.querySelector('.empty-chat');
        if (emptyState) emptyState.remove();

        messageList.appendChild(buildMessageElement(data));
        scrollChatToBottom();
    });

    socket.on('typing', function (data) {
        if (String(data.user_id) === document.body.dataset.userId) return;
        // فعلاً فقط لاگ — نمایش واقعی typing indicator در فاز بعد (طبق نقشه راه)
        console.debug(`${data.username} is typing...`);
    });

    socket.connect();

    /*
    |----------------------------------------------------------------
    | Send a new message via HTTP POST (session-authenticated)
    |----------------------------------------------------------------
    */

    const form = document.querySelector('.chat-composer');
    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();

            const input = form.querySelector('input[name="content"]');
            const content = input.value.trim();
            if (!content) return;

            const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

            const response = await fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `content=${encodeURIComponent(content)}`,
            });

            if (response.ok) {
                input.value = '';
            }
        });
    }
});

/*
|--------------------------------------------------------------------------
| Enter = Send
|--------------------------------------------------------------------------
*/

document.addEventListener('keydown', function (event) {
    const target = event.target;

    if (target.matches('.composer-input input')) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            const form = target.closest('form');
            if (form) {
                form.requestSubmit();
            }
        }
    }
});