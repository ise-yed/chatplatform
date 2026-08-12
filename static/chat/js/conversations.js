document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("conversationSearch");
    const conversations = document.querySelectorAll(".conversation-card");

    if (!searchInput) return;

    searchInput.addEventListener("input", function () {
        const query = this.value.trim().toLowerCase();

        conversations.forEach(function (conversation) {
            const title = conversation.dataset.conversation || "";
            conversation.style.display =
                title.includes(query)
                    ? "flex"
                    : "none";
        });
    });
});