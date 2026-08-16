class ChatSocket {
    constructor(url, options = {}) {
        this.url = url;
        this.socket = null;
        this.handlers = {};
        this.reconnectDelay = options.reconnectDelay || 2000;
        this.shouldReconnect = true;
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

        this.socket.addEventListener('close', () => {
            if (!this.shouldReconnect) return;
            setTimeout(() => this.connect(), this.reconnectDelay);
        });

        return this;
    }

    disconnect() {
        this.shouldReconnect = false;
        if (this.socket) this.socket.close();
    }
}