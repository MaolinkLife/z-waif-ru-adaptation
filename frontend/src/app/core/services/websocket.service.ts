import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({
    providedIn: 'root'
})
export class WebsocketService {
    private socket: WebSocket | null = null;
    private messageQueue: string[] = [];

    messages$ = new Subject<string>();

    connect(): void {
        if (this.socket) return; // чтобы второй раз не коннектился

        this.socket = new WebSocket(`ws://${window.location.host}/api/ws`);

        this.socket.onopen = () => {
            console.log('[WS] ✅ Connected');
            const sock = this.socket;  // сохранили ссылку
            while (this.messageQueue.length > 0) {
                const msg = this.messageQueue.shift();
                if (msg && sock) sock.send(msg);
            }
        };

        this.socket.onmessage = (event) => {
            // console.log('[WS] Message:', event.data);
            this.messages$.next(event.data);
        };

        this.socket.onerror = (error) => {
            console.error('[WS] ❌ Error:', error);
        };

        this.socket.onclose = () => {
            console.log('[WS] ⚠️ Disconnected');
            this.socket = null;
        };
    }

    send(message: string): void {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(message);
        } else {
            console.warn('[WS] ⛔ Not connected yet, queueing message');
            this.messageQueue.push(message);
        }
    }

    disconnect(): void {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}
