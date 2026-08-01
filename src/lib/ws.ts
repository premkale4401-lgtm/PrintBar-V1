/**
 * PrintBar — WebSocket Client
 *
 * Wraps the native WebSocket with:
 * - Authenticated connection (token passed as query param)
 * - Exponential back-off reconnection (max 30s)
 * - Typed event emitter for job status events
 * - Heartbeat / ping handling
 *
 * Usage:
 *   const ws = createJobWebSocket(sessionId, token, handlers);
 *   ws.connect();
 *   // later:
 *   ws.disconnect();
 */

import { WS_URL } from './env';

// ─── Event Types (matches backend doc 11) ────────────────────────────────────

export type WsEventType =
  | 'JOB_ASSIGNED'
  | 'DOWNLOADING'
  | 'PRINTING'
  | 'PAGE_PROGRESS'
  | 'COMPLETED'
  | 'FAILED'
  | 'HEARTBEAT'
  | 'ERROR';

export interface WsJobEvent {
  type: WsEventType;
  jobId?: string;
  status?: string;
  progress?: number;         // 0-100 for PAGE_PROGRESS
  currentPage?: number;
  totalPages?: number;
  message?: string;
  timestamp?: string;
}

export interface WsHandlers {
  onEvent: (event: WsJobEvent) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
  onError?: (error: Event) => void;
}

// ─── WebSocket Client ─────────────────────────────────────────────────────────

const INITIAL_RETRY_DELAY_MS = 1_000;
const MAX_RETRY_DELAY_MS = 30_000;
const MAX_RETRY_ATTEMPTS = 10;

export interface PrintBarWebSocket {
  connect(): void;
  disconnect(): void;
  isConnected(): boolean;
}

export function createJobWebSocket(
  sessionId: string,
  token: string,
  handlers: WsHandlers,
): PrintBarWebSocket {
  let socket: WebSocket | null = null;
  let retryCount = 0;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let intentionallyClosed = false;

  function buildUrl(): string {
    const base = WS_URL.replace(/^http/, 'ws');
    return `${base}/api/v1/ws/kiosk/${sessionId}?token=${encodeURIComponent(token)}`;
  }

  function scheduleReconnect(): void {
    if (intentionallyClosed || retryCount >= MAX_RETRY_ATTEMPTS) return;

    const delay = Math.min(
      INITIAL_RETRY_DELAY_MS * 2 ** retryCount,
      MAX_RETRY_DELAY_MS,
    );
    retryCount += 1;

    retryTimer = setTimeout(() => {
      if (!intentionallyClosed) {
        openSocket();
      }
    }, delay);
  }

  function openSocket(): void {
    if (socket && socket.readyState === WebSocket.OPEN) return;

    socket = new WebSocket(buildUrl());

    socket.onopen = () => {
      retryCount = 0;
      handlers.onConnected?.();
    };

    socket.onmessage = (event) => {
      try {
        const data: WsJobEvent = JSON.parse(event.data as string);
        handlers.onEvent(data);
      } catch {
        // Ignore malformed messages.
      }
    };

    socket.onclose = () => {
      if (!intentionallyClosed) {
        handlers.onDisconnected?.();
        scheduleReconnect();
      }
    };

    socket.onerror = (error) => {
      handlers.onError?.(error);
      // onclose will also fire — reconnect handled there.
    };
  }

  return {
    connect() {
      intentionallyClosed = false;
      retryCount = 0;
      openSocket();
    },

    disconnect() {
      intentionallyClosed = true;
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      if (socket) {
        socket.close();
        socket = null;
      }
    },

    isConnected() {
      return socket?.readyState === WebSocket.OPEN;
    },
  };
}
