/**
 * PrintBar — usePaymentPolling Hook
 *
 * Polls /api/v1/payments/{jobId}/status every 2.5 seconds after payment.
 * Drives the "Verifying Payment..." → "✓ Payment Verified" transition.
 *
 * Architecture:
 *   - Backend is ALWAYS the authority — frontend never marks payment successful.
 *   - Polling stops when verificationStage reaches VERIFIED, FAILED, or CANCELLED.
 *   - Timeout after 90 seconds (handles webhook delays gracefully).
 *   - No busy-waits — uses setInterval with cleanup on unmount.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { paymentService, VerificationStage, PaymentStatusResult } from '../services/payment.service';

export type PollingStatus =
  | 'idle'       // Not started
  | 'polling'    // Actively polling
  | 'verified'   // Backend confirmed payment SUCCESS
  | 'failed'     // Payment failed
  | 'cancelled'  // User cancelled
  | 'expired'    // Payment order expired
  | 'timeout'    // Polling timed out (webhook delay > 90s)
  | 'error';     // Network/unexpected error

export interface UsePaymentPollingResult {
  /** Start polling for this jobId. */
  startPolling: (jobId: string) => void;
  /** Stop polling immediately. */
  stopPolling: () => void;
  /** Current polling status. */
  pollingStatus: PollingStatus;
  /** Raw verification stage from backend. */
  verificationStage: VerificationStage | null;
  /** Full status result from last successful poll. */
  lastStatus: PaymentStatusResult | null;
  /** Error message if pollingStatus is 'error'. */
  errorMessage: string | null;
  /** Elapsed seconds since polling started. */
  elapsedSeconds: number;
}

const POLL_INTERVAL_MS = 2500;       // Poll every 2.5 seconds.
const POLL_TIMEOUT_MS = 90_000;      // Stop after 90 seconds (webhook may be delayed).
const TERMINAL_STAGES: VerificationStage[] = ['VERIFIED', 'FAILED', 'CANCELLED', 'EXPIRED'];

export function usePaymentPolling(): UsePaymentPollingResult {
  const [pollingStatus, setPollingStatus] = useState<PollingStatus>('idle');
  const [verificationStage, setVerificationStage] = useState<VerificationStage | null>(null);
  const [lastStatus, setLastStatus] = useState<PaymentStatusResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTimeRef = useRef<number>(0);
  const elapsedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentJobIdRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (elapsedIntervalRef.current) {
      clearInterval(elapsedIntervalRef.current);
      elapsedIntervalRef.current = null;
    }
    currentJobIdRef.current = null;
  }, []);

  const startPolling = useCallback((jobId: string) => {
    // Clear any existing polling.
    stopPolling();

    currentJobIdRef.current = jobId;
    startTimeRef.current = Date.now();
    setPollingStatus('polling');
    setVerificationStage(null);
    setLastStatus(null);
    setErrorMessage(null);
    setElapsedSeconds(0);

    // Elapsed seconds counter for UI display.
    elapsedIntervalRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);

    const poll = async () => {
      if (currentJobIdRef.current !== jobId) return; // Stale poll — stop.

      try {
        const status = await paymentService.getPaymentStatus(jobId);

        if (currentJobIdRef.current !== jobId) return; // Check again after await.

        setLastStatus(status);
        setVerificationStage(status.verificationStage);

        // Map verification stage to polling status.
        switch (status.verificationStage) {
          case 'VERIFIED':
            setPollingStatus('verified');
            stopPolling();
            return;
          case 'FAILED':
            setPollingStatus('failed');
            setErrorMessage('Payment failed. Please try again.');
            stopPolling();
            return;
          case 'CANCELLED':
            setPollingStatus('cancelled');
            setErrorMessage('Payment was cancelled.');
            stopPolling();
            return;
          case 'EXPIRED':
            setPollingStatus('expired');
            setErrorMessage('Payment session expired. Please start again.');
            stopPolling();
            return;
          default:
            // PENDING or VERIFYING — keep polling.
            break;
        }
      } catch (err) {
        // Network error — log and keep polling (transient failures shouldn't stop us).
        console.warn('[usePaymentPolling] Poll error (retrying):', err);
      }
    };

    // Kick off immediately, then on interval.
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    // Global timeout — stop after 90 seconds.
    timeoutRef.current = setTimeout(() => {
      if (currentJobIdRef.current === jobId) {
        setPollingStatus('timeout');
        setErrorMessage('Verification is taking longer than expected. Please check with the counter.');
        stopPolling();
      }
    }, POLL_TIMEOUT_MS);
  }, [stopPolling]);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  return {
    startPolling,
    stopPolling,
    pollingStatus,
    verificationStage,
    lastStatus,
    errorMessage,
    elapsedSeconds,
  };
}
