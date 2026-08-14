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
        statusEl.innerHTML = '<i class="bi bi-check2"></i>';
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
function createTypingController(socket, input) {
    let stopTypingTimer = null;
    let isTyping = false;

    function startTyping() {
        if (!isTyping) {
            isTyping = true;
            socket.emit('typing.start', {});
        }

        clearTimeout(stopTypingTimer);

        stopTypingTimer = setTimeout(() => {
            stopTyping();
        }, 1500);
    }

    function stopTyping() {
        if (!isTyping) return;

        isTyping = false;
        clearTimeout(stopTypingTimer);
        stopTypingTimer = null;

        socket.emit('typing.stop', {});
    }

    input.addEventListener('input', function () {
        if (!this.value.trim()) {
            stopTyping();
            return;
        }

        startTyping();
    });

    input.addEventListener('blur', function () {
        stopTyping();
    });

    return {
        stop: stopTyping,
    };
}


document.addEventListener('DOMContentLoaded', function () {
    scrollChatToBottom();

    const chatWindow = document.querySelector('.chat-window');
    if (!chatWindow) return;

    const conversationId = chatWindow.dataset.conversationId;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new ChatSocket(`${protocol}//${window.location.host}/ws/chat/${conversationId}/`);

    const form = document.querySelector('.chat-composer');
    let typingController = null;

    if (form) {
        const input = form.querySelector('input[name="content"]');

        if (input) {
            typingController = createTypingController(socket, input);
        }
    }

    socket.on('message.new', function (data) {
        const messageList = document.getElementById('message-list');
        if (!messageList) return;

        const emptyState = messageList.querySelector('.empty-chat');
        if (emptyState) emptyState.remove();

        messageList.appendChild(buildMessageElement(data));
        scrollChatToBottom();
        
        if (document.visibilityState === 'visible' && String(data.sender_id) !== document.body.dataset.userId) {
            socket.emit('seen', { message_id: data.id });
        }
    });

    socket.on('typing', function (data) {
        if (String(data.user_id) === document.body.dataset.userId) return;

        const statusText = document.getElementById('chat-status-text');

        if (!statusText) return;

        if (data.is_typing) {
            statusText.textContent = `${data.username} در حال نوشتن...`;
        } else {
            statusText.textContent = 'آنلاین';
        }
    });

    socket.on('read_receipt', function (data) {
    if (data.user_id === document.body.dataset.userId) return; // echo خودمون رو نادیده بگیر
    markMessagesAsSeen(data.last_read_message_id);
});
    document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
        socket.emit('seen', {});
    }
});

    socket.connect();

    /*
    |----------------------------------------------------------------
    | Send a new message via HTTP POST (session-authenticated)
    |----------------------------------------------------------------
    */

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
                if (typingController) {
                    typingController.stop();
                }

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


function markMessagesAsSeen(lastReadMessageId) {
    const messageList = document.getElementById('message-list');
    if (!messageList) return;

    const myMessages = Array.from(messageList.querySelectorAll('.message-row.message-me'));
    const targetIndex = myMessages.findIndex((el) => el.dataset.messageId === lastReadMessageId);
    if (targetIndex === -1) return;

    myMessages.slice(0, targetIndex + 1).forEach((el) => {
        const status = el.querySelector('.message-status');
        if (!status) return;
        status.title = 'دیده شد';
        status.innerHTML = '<i class="bi bi-check2-all" style="color:#60a5fa"></i>';
    });
}