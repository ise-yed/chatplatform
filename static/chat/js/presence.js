/*
|--------------------------------------------------------------------------
| App-level Presence
|--------------------------------------------------------------------------
|
| This socket is completely independent from the conversation socket.
|
| Responsibilities:
|
| - online
| - offline
| - last seen
| - online dots
| - status text
|
| It does NOT handle:
|
| - messages
| - typing
| - seen
|
|--------------------------------------------------------------------------
*/

document.addEventListener('DOMContentLoaded', function () {

    /*
    |--------------------------------------------------------------------------
    | Current logged-in user
    |--------------------------------------------------------------------------
    */

    const currentUserId =
        document.body.dataset.userId;


    /*
    | Anonymous pages do not need Presence.
    */

    if (!currentUserId) {
        return;
    }


    /*
    |--------------------------------------------------------------------------
    | WebSocket protocol
    |--------------------------------------------------------------------------
    */

    const protocol =
        window.location.protocol === 'https:'
            ? 'wss:'
            : 'ws:';


    /*
    |--------------------------------------------------------------------------
    | Presence socket
    |--------------------------------------------------------------------------
    */

    const presenceSocket =
        new ChatSocket(
            `${protocol}//${window.location.host}/ws/presence/`
        );


    /*
    |--------------------------------------------------------------------------
    | PRESENCE UPDATE
    |--------------------------------------------------------------------------
    */

    presenceSocket.on(
        'presence.update',
        function (data) {

            /*
            | ID of the user whose status changed.
            */

            const targetUserId =
                String(data.user_id);


            /*
            |--------------------------------------------------------------------------
            | ONLINE DOTS
            |--------------------------------------------------------------------------
            */

            document
                .querySelectorAll(
                    `[data-user-online="${targetUserId}"]`
                )
                .forEach(function (element) {

                    /*
                    | Case 1:
                    |
                    | <span class="status-dot"
                    |       data-user-online="12">
                    |
                    */

                    if (
                        element.classList.contains(
                            'status-dot'
                        )
                    ) {

                        updateDot(
                            element,
                            data.is_online
                        );

                        return;
                    }


                    /*
                    | Case 2:
                    |
                    | <div
                    |     class="chat-page-avatar"
                    |     data-user-online="12"
                    | >
                    |     <span class="chat-online-dot">
                    |     </span>
                    | </div>
                    |
                    */

                    const dot =
                        element.querySelector(
                            '.chat-online-dot'
                        );


                    if (!dot) {
                        return;
                    }


                    updateDot(
                        dot,
                        data.is_online
                    );

                });


            /*
            |--------------------------------------------------------------------------
            | STATUS TEXT
            |--------------------------------------------------------------------------
            */

            document
                .querySelectorAll(
                    `[data-user-online-text="${targetUserId}"]`
                )
                .forEach(function (element) {

                    const text =
                        buildPresenceText(data);


                    /*
                    | Save latest real Presence state.
                    |
                    | chat.js does not use this yet.
                    | We keep it here for future integration.
                    */

                    element.dataset.presenceText =
                        text;


                    /*
                    | Do NOT overwrite typing text.
                    |
                    | chat.js owns typing.
                    */

                    if (
                        element.dataset.typing ===
                        'true'
                    ) {
                        return;
                    }


                    element.textContent = text;

                });

        }
    );


    /*
    |--------------------------------------------------------------------------
    | CONNECT
    |--------------------------------------------------------------------------
    */

    presenceSocket.connect();

});


/*
|--------------------------------------------------------------------------
| Update Dot
|--------------------------------------------------------------------------
*/

function updateDot(element, isOnline) {

    /*
    | Main class used by the current CSS.
    */

    element.classList.toggle(
        'is-online',
        Boolean(isOnline)
    );


    /*
    | Compatibility classes.
    */

    element.classList.toggle(
        'online',
        Boolean(isOnline)
    );


    element.classList.toggle(
        'offline',
        !isOnline
    );

}


/*
|--------------------------------------------------------------------------
| Build Presence Text
|--------------------------------------------------------------------------
*/

function buildPresenceText(data) {

    /*
    |--------------------------------------------------------------------------
    | Online
    |--------------------------------------------------------------------------
    */

    if (data.is_online) {
        return 'آنلاین';
    }


    /*
    |--------------------------------------------------------------------------
    | Offline + Last Seen
    |--------------------------------------------------------------------------
    */

    if (data.last_seen) {

        const time =
            new Date(
                data.last_seen
            ).toLocaleTimeString(
                'fa-IR',
                {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false,
                }
            );


        return `آخرین بازدید: ${time}`;
    }


    /*
    |--------------------------------------------------------------------------
    | Offline with no last seen
    |--------------------------------------------------------------------------
    */

    return 'آفلاین';
}