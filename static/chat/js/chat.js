/*
|--------------------------------------------------------------------------
| Scroll chat to bottom
|--------------------------------------------------------------------------
*/

function scrollChatToBottom() {
    const container = document.getElementById('chat-messages');

    if (!container) {
        return;
    }

    container.scrollTop = container.scrollHeight;
}


/*
|--------------------------------------------------------------------------
| Build message element
|--------------------------------------------------------------------------
*/

function buildMessageElement(message) {

    const isMe =
        String(message.sender_id) ===
        String(document.body.dataset.userId);


    const row = document.createElement('div');

    row.className =
        `message-row ${isMe ? 'message-me' : 'message-other'}`;

    row.dataset.messageId = message.id;


    /*
    |--------------------------------------------------------------------------
    | Other user's avatar
    |--------------------------------------------------------------------------
    */

    if (!isMe) {

        const avatar = document.createElement('div');

        avatar.className = 'message-avatar';

        avatar.textContent =
            message.sender_username.charAt(0).toUpperCase();

        row.appendChild(avatar);
    }


    /*
    |--------------------------------------------------------------------------
    | Content
    |--------------------------------------------------------------------------
    */

    const contentWrap = document.createElement('div');

    contentWrap.className = 'message-content';


    /*
    |--------------------------------------------------------------------------
    | Sender
    |--------------------------------------------------------------------------
    */

    if (!isMe) {

        const senderEl = document.createElement('div');

        senderEl.className = 'message-sender';

        senderEl.textContent =
            message.sender_username;

        contentWrap.appendChild(senderEl);
    }


    /*
    |--------------------------------------------------------------------------
    | Bubble
    |--------------------------------------------------------------------------
    */

    const bubble = document.createElement('div');

    bubble.className = 'message-bubble';


    /*
    |--------------------------------------------------------------------------
    | Message text
    |--------------------------------------------------------------------------
    */

    const textEl = document.createElement('div');

    textEl.className = 'message-text';

    textEl.textContent = message.content;

    bubble.appendChild(textEl);


    /*
    |--------------------------------------------------------------------------
    | Meta
    |--------------------------------------------------------------------------
    */

    const meta = document.createElement('div');

    meta.className = 'message-meta';


    /*
    |--------------------------------------------------------------------------
    | Time
    |--------------------------------------------------------------------------
    */

    const timeEl = document.createElement('span');

    timeEl.className = 'message-time';

    timeEl.textContent =
        new Date(message.created_at)
            .toLocaleTimeString('fa-IR', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false,
            });

    meta.appendChild(timeEl);


    /*
    |--------------------------------------------------------------------------
    | Message status
    |--------------------------------------------------------------------------
    */

    if (isMe) {

        const statusEl = document.createElement('span');

        statusEl.className = 'message-status';

        statusEl.title = 'ارسال شده';

        statusEl.innerHTML =
            '<i class="bi bi-check2"></i>';

        meta.appendChild(statusEl);
    }


    bubble.appendChild(meta);

    contentWrap.appendChild(bubble);

    row.appendChild(contentWrap);


    return row;
}


/*
|--------------------------------------------------------------------------
| Typing Controller
|--------------------------------------------------------------------------
*/

function createTypingController(socket, input) {

    let stopTypingTimer = null;

    let isTyping = false;


    /*
    |--------------------------------------------------------------------------
    | Start typing
    |--------------------------------------------------------------------------
    */

    function startTyping() {

        if (!isTyping) {

            isTyping = true;

            socket.emit('typing.start', {});
        }


        clearTimeout(stopTypingTimer);


        stopTypingTimer = setTimeout(function () {

            stopTyping();

        }, 1500);
    }


    /*
    |--------------------------------------------------------------------------
    | Stop typing
    |--------------------------------------------------------------------------
    */

    function stopTyping() {

        if (!isTyping) {
            return;
        }


        isTyping = false;


        clearTimeout(stopTypingTimer);

        stopTypingTimer = null;


        socket.emit('typing.stop', {});
    }


    /*
    |--------------------------------------------------------------------------
    | Input event
    |--------------------------------------------------------------------------
    */

    input.addEventListener('input', function () {

        if (!this.value.trim()) {

            stopTyping();

            return;
        }


        startTyping();
    });


    /*
    |--------------------------------------------------------------------------
    | Blur
    |--------------------------------------------------------------------------
    */

    input.addEventListener('blur', function () {

        stopTyping();

    });


    return {
        stop: stopTyping,
    };
}


/*
|--------------------------------------------------------------------------
| Main Chat
|--------------------------------------------------------------------------
*/

document.addEventListener('DOMContentLoaded', function () {

    /*
    |--------------------------------------------------------------------------
    | Initial scroll
    |--------------------------------------------------------------------------
    */

    scrollChatToBottom();


    /*
    |--------------------------------------------------------------------------
    | Chat window
    |--------------------------------------------------------------------------
    */

    const chatWindow =
        document.querySelector('.chat-window');


    if (!chatWindow) {
        return;
    }


    /*
    |--------------------------------------------------------------------------
    | Conversation ID
    |--------------------------------------------------------------------------
    */

    const conversationId =
        chatWindow.dataset.conversationId;


    if (!conversationId) {
        return;
    }


    /*
    |--------------------------------------------------------------------------
    | WebSocket URL
    |--------------------------------------------------------------------------
    */

    const protocol =
        window.location.protocol === 'https:'
            ? 'wss:'
            : 'ws:';


    const socket =
        new ChatSocket(
            `${protocol}//${window.location.host}/ws/chat/${conversationId}/`
        );


    /*
    |--------------------------------------------------------------------------
    | Composer
    |--------------------------------------------------------------------------
    */

    const form =
        document.querySelector('.chat-composer');


    let typingController = null;


    if (form) {

        const input =
            form.querySelector(
                'input[name="content"]'
            );


        if (input) {

            typingController =
                createTypingController(
                    socket,
                    input
                );
        }
    }


    /*
    |--------------------------------------------------------------------------
    | NEW MESSAGE
    |--------------------------------------------------------------------------
    */

    socket.on('message.new', function (data) {

        const messageList =
            document.getElementById('message-list');


        if (!messageList) {
            return;
        }


        const emptyState =
            messageList.querySelector('.empty-chat');


        if (emptyState) {
            emptyState.remove();
        }


        messageList.appendChild(
            buildMessageElement(data)
        );


        scrollChatToBottom();


        /*
        | Mark received message as seen
        */

        if (
            document.visibilityState === 'visible' &&
            String(data.sender_id) !==
                String(document.body.dataset.userId)
        ) {

            socket.emit('seen', {
                message_id: data.id
            });
        }

    });


    /*
    |--------------------------------------------------------------------------
    | TYPING
    |--------------------------------------------------------------------------
    */

    socket.on('typing', function (data) {

        /*
        | Ignore our own typing event
        */

        if (
            String(data.user_id) ===
            String(document.body.dataset.userId)
        ) {
            return;
        }


        const statusText =
            document.getElementById(
                'chat-status-text'
            );


        if (!statusText) {
            return;
        }


        if (data.is_typing) {

            statusText.textContent =
                `${data.username} در حال نوشتن...`;

        } else {

            statusText.textContent =
                'آنلاین';

        }

    });


    /*
    |--------------------------------------------------------------------------
    | READ RECEIPT
    |--------------------------------------------------------------------------
    */

    socket.on('read_receipt', function (data) {

        if (
            String(data.user_id) ===
            String(document.body.dataset.userId)
        ) {
            return;
        }


        markMessagesAsSeen(
            data.last_read_message_id
        );
    });


    /*
    |--------------------------------------------------------------------------
    | Visibility change
    |--------------------------------------------------------------------------
    */

    document.addEventListener(
        'visibilitychange',
        function () {

            if (
                document.visibilityState ===
                'visible'
            ) {

                socket.emit('seen', {});
            }
        }
    );


    /*
    |--------------------------------------------------------------------------
    | CONNECT
    |--------------------------------------------------------------------------
    */

    socket.connect();


    /*
    |--------------------------------------------------------------------------
    | SEND MESSAGE
    |--------------------------------------------------------------------------
    | Message persistence remains HTTP POST.
    |--------------------------------------------------------------------------
    */

    if (form) {

        form.addEventListener(
            'submit',
            async function (event) {

                event.preventDefault();


                const input =
                    form.querySelector(
                        'input[name="content"]'
                    );


                if (!input) {
                    return;
                }


                const content =
                    input.value.trim();


                if (!content) {
                    return;
                }


                const csrfInput =
                    form.querySelector(
                        'input[name="csrfmiddlewaretoken"]'
                    );


                if (!csrfInput) {
                    return;
                }


                const csrfToken =
                    csrfInput.value;


                try {

                    const response =
                        await fetch(
                            form.action,
                            {
                                method: 'POST',

                                credentials: 'same-origin',

                                headers: {
                                    'X-CSRFToken':
                                        csrfToken,

                                    'Content-Type':
                                        'application/x-www-form-urlencoded',
                                },

                                body:
                                    `content=${encodeURIComponent(content)}`,
                            }
                        );


                    if (response.ok) {

                        if (typingController) {
                            typingController.stop();
                        }


                        input.value = '';
                    }

                } catch (error) {

                    console.error(
                        'Message send failed:',
                        error
                    );
                }

            }
        );
    }

});


/*
|--------------------------------------------------------------------------
| Enter = Send
|--------------------------------------------------------------------------
*/

document.addEventListener(
    'keydown',
    function (event) {

        const target = event.target;


        if (
            !target.matches(
                '.composer-input input'
            )
        ) {
            return;
        }


        if (
            event.key === 'Enter' &&
            !event.shiftKey
        ) {

            event.preventDefault();


            const form =
                target.closest('form');


            if (form) {
                form.requestSubmit();
            }
        }

    }
);


/*
|--------------------------------------------------------------------------
| Mark Messages As Seen
|--------------------------------------------------------------------------
*/

function markMessagesAsSeen(lastReadMessageId) {

    const messageList =
        document.getElementById(
            'message-list'
        );


    if (!messageList) {
        return;
    }


    const myMessages =
        Array.from(
            messageList.querySelectorAll(
                '.message-row.message-me'
            )
        );


    const targetIndex =
        myMessages.findIndex(
            function (element) {

                return (
                    String(element.dataset.messageId) ===
                    String(lastReadMessageId)
                );
            }
        );


    if (targetIndex === -1) {
        return;
    }


    myMessages
        .slice(0, targetIndex + 1)
        .forEach(function (element) {

            const status =
                element.querySelector(
                    '.message-status'
                );


            if (!status) {
                return;
            }


            status.title = 'دیده شد';


            status.innerHTML =
                '<i class="bi bi-check2-all" style="color:#60a5fa"></i>';
        });

}