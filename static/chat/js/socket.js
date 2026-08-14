/*
|--------------------------------------------------------------------------
| Minimal event-based WebSocket wrapper
|--------------------------------------------------------------------------
| Every message on the wire (both directions) is a small JSON envelope:
|     {"event": "<name>", "data": {...}}
| .on(eventName, handler) registers a listener; .emit sends one. This
| keeps consumers.py and every page's JS speaking the same event
| vocabulary — adding a new real-time feature (typing, seen, presence)
| is just one more handler, no changes to the transport itself.
*/

class ChatSocket {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.handlers = {};
    }

    on(eventName, handler) {
        if (!this.handlers[eventName]) {
            this.handlers[eventName] = [];
        }
        this.handlers[eventName].push(handler);
        return this;
    }

    emit(eventName, data) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            return;
        }
        this.socket.send(JSON.stringify({ event: eventName, data: data || {} }));
    }

    connect() {
        this.socket = new WebSocket(this.url);

        this.socket.addEventListener('message', (rawEvent) => {
            let payload;
            try {
                payload = JSON.parse(rawEvent.data);
            } catch (error) {
                return;
            }
            (this.handlers[payload.event] || []).forEach((handler) => handler(payload.data));
        });

        return this;
    }
}