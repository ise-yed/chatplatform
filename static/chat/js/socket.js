class ChatSocket {
    constructor(url, options = {}) {
        this.url = url;
        this.socket = null;
        this.handlers = {};

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, then capped at 30s.
        // The delay resets to the base as soon as a connection succeeds,
        // so a brief blip doesn't leave us waiting 30s after recovery.
        this.baseReconnectDelay = options.baseReconnectDelay || 1000;
        this.maxReconnectDelay = options.maxReconnectDelay || 30000;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;

        this.shouldReconnect = true;

        // 'closed' | 'connecting' | 'open' — used to guarantee at most one
        // live socket and at most one pending reconnect at a time.
        this.state = 'closed';
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
        // Guard against concurrent connects: never open a second socket
        // while one is connecting or already open.
        if (this.state === 'connecting' || this.state === 'open') {
            return this;
        }

        this._clearReconnectTimer();
        this.state = 'connecting';
        this.socket = new WebSocket(this.url);

        this.socket.addEventListener('open', () => {
            this.state = 'open';
            // Successful connection — reset the backoff.
            this.reconnectAttempts = 0;
        });

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
            this.state = 'closed';
            this.socket = null;
            if (!this.shouldReconnect) {
                return;
            }
            this._scheduleReconnect();
        });

        return this;
    }

    _scheduleReconnect() {
        // Only ever one pending reconnect at a time.
        if (this.reconnectTimer !== null) {
            return;
        }

        const delay = Math.min(
            this.maxReconnectDelay,
            this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts)
        );
        this.reconnectAttempts += 1;

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }

    _clearReconnectTimer() {
        if (this.reconnectTimer !== null) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }

    disconnect() {
        this.shouldReconnect = false;
        this._clearReconnectTimer();
        if (this.socket) {
            this.socket.close();
        }
    }
}
