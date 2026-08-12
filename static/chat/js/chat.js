/*
|--------------------------------------------------------------------------
| Scroll chat to bottom
|--------------------------------------------------------------------------
*/

function scrollChatToBottom() {
    const container = document.getElementById("chat-messages");
    if (!container) return;
    container.scrollTop = container.scrollHeight;
}


/*
|--------------------------------------------------------------------------
| Initial scroll
|--------------------------------------------------------------------------
*/

document.addEventListener("DOMContentLoaded", function () {
    scrollChatToBottom();
});


/*
|--------------------------------------------------------------------------
| Scroll after HTMX message
|--------------------------------------------------------------------------
*/

document.body.addEventListener("htmx:afterSwap", function (event) {
    if (
        event.detail.target &&
        event.detail.target.id === "message-list"
    ) {
        scrollChatToBottom();
    }
});


/*
|--------------------------------------------------------------------------
| Enter = Send
|--------------------------------------------------------------------------
*/

document.addEventListener("keydown", function (event) {
    const target = event.target;

    if (target.matches(".composer-input input")) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            const form = target.closest("form");
            if (form) {
                form.requestSubmit();
            }
        }
    }
});