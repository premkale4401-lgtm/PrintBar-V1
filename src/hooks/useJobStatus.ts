/**
 * PrintBar — useJobStatus hook
 *
 * Connects WebSocket to /api/v1/ws/kiosk/{sessionId} for real-time job updates.
 * Falls back to polling GET /payments/{jobId}/status every 3s if WS fails.
 *
 * Returns the current job state so StepPrinting can drive the checklist.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { createJobWebSocket, WsJobEvent, PrintBarWebSocket } from '../lib/ws';
import { paymentService, PaymentStatus } from '../services/payment.service';
import { sessionService } from '../services/session.service';

// ─── Job Status Progression ───────────────────────────────────────────────────

export type JobProgressStatus =
  | 'QUEUED'
  | 'ASSIGNED'
  | 'DOWNLOADING'
  | 'PRINTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export interface JobStatusState {
  jobStatus: JobProgressStatus | null;
  paymentStatus: string | null;
  pageProgress: number;      // 0-100
  currentPage: number;
  totalPages: number;
  message: string | null;
  wsConnected: boolean;
  isPolling: boolean;
  error: string | null;
}

interface UseJobStatusReturn extends JobStatusState {
  retryConnection: () => void;
}

interface UseJobStatusOptions {
  jobId: string | null;
  sessionId: string | null;
  enabled?: boolean;
}

const POLL_INTERVAL_MS = 3_000;

export function useJobStatus({
  jobId,
  sessionId,
  enabled = true,
}: UseJobStatusOptions): UseJobStatusReturn {
  const [state, setState] = useState<JobStatusState>({
    jobStatus: null,
    paymentStatus: null,
    pageProgress: 0,
    currentPage: 0,
    totalPages: 0,
    message: null,
    wsConnected: false,
    isPolling: false,
    error: null,
  });

  const wsRef = useRef<PrintBarWebSocket | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsFailed = useRef(false);

  const pollErrorCountRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
      setState((prev) => ({ ...prev, isPolling: false }));
    }
  }, []);

  const startPolling = useCallback(() => {
    if (!jobId || pollTimerRef.current !== null) return;

    setState((prev) => ({ ...prev, isPolling: true, error: null }));
    pollErrorCountRef.current = 0;

    const poll = async () => {
      if (!jobId) return;
      try {
        const status: PaymentStatus = await paymentService.getPaymentStatus(jobId);
        pollErrorCountRef.current = 0; // reset on success
        setState((prev) => ({
          ...prev,
          jobStatus: status.jobStatus as JobProgressStatus,
          paymentStatus: status.paymentStatus,
          error: null,
        }));

        // Stop polling once terminal state is reached.
        if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(status.jobStatus)) {
          stopPolling();
        }
      } catch {
        pollErrorCountRef.current += 1;
        if (pollErrorCountRef.current >= 5) {
          stopPolling();
          setState((prev) => ({
            ...prev,
            error: 'Connection to server lost. Please retry or contact support.',
            isPolling: false,
            wsConnected: false,
          }));
        }
      }
    };

    poll();
    pollTimerRef.current = setInterval(poll, POLL_INTERVAL_MS);
  }, [jobId, stopPolling]);

  const retryConnection = useCallback(() => {
    if (!wsRef.current?.isConnected()) {
      startPolling();
    }
  }, [startPolling]);

  const handleWsEvent = useCallback((event: WsJobEvent) => {
    setState((prev) => {
      const next = { ...prev };

      switch (event.type) {
        case 'JOB_ASSIGNED':
          next.jobStatus = 'ASSIGNED';
          break;
        case 'DOWNLOADING':
          next.jobStatus = 'DOWNLOADING';
          break;
        case 'PRINTING':
          next.jobStatus = 'PRINTING';
          break;
        case 'PAGE_PROGRESS':
          next.jobStatus = 'PRINTING';
          next.currentPage = event.currentPage ?? prev.currentPage;
          next.totalPages = event.totalPages ?? prev.totalPages;
          next.pageProgress =
            event.progress ??
            (event.totalPages
              ? Math.round(((event.currentPage ?? 0) / event.totalPages) * 100)
              : prev.pageProgress);
          break;
        case 'COMPLETED':
          next.jobStatus = 'COMPLETED';
          next.pageProgress = 100;
          break;
        case 'FAILED':
          next.jobStatus = 'FAILED';
          next.message = event.message ?? 'Print job failed.';
          break;
        default:
          break;
      }

      return next;
    });
  }, []);

  useEffect(() => {
    if (!enabled || !jobId || !sessionId) return;

    const token = sessionService.getToken();
    if (!token) {
      // No token — fall back immediately to polling.
      wsFailed.current = true;
      startPolling();
      return;
    }

    const ws = createJobWebSocket(sessionId, token, {
      onEvent: handleWsEvent,
      onConnected: () => {
        wsFailed.current = false;
        setState((prev) => ({ ...prev, wsConnected: true, isPolling: false }));
        stopPolling(); // Stop polling if we reconnect.
      },
      onDisconnected: () => {
        setState((prev) => ({ ...prev, wsConnected: false }));
        // If WebSocket dropped and job is still active, fall back to polling.
        if (!wsFailed.current) {
          wsFailed.current = true;
          startPolling();
        }
      },
      onError: () => {
        wsFailed.current = true;
        startPolling();
      },
    });

    wsRef.current = ws;
    ws.connect();

    // Safety net: if WS doesn't connect within 5s, start polling.
    const connectTimeout = setTimeout(() => {
      if (!wsRef.current?.isConnected()) {
        startPolling();
      }
    }, 5_000);

    return () => {
      clearTimeout(connectTimeout);
      ws.disconnect();
      wsRef.current = null;
      stopPolling();
    };
  }, [enabled, jobId, sessionId, handleWsEvent, startPolling, stopPolling]);

  return { ...state, retryConnection };
}
