/**
 * PrintBar — useGuestSession hook
 *
 * Creates a guest session JWT on mount (when the user lands on /kiosk).
 * Exposes the token and sessionId for downstream hooks (upload, WebSocket).
 *
 * - If a valid token already exists in sessionStorage, it is reused.
 * - Session creation runs only once per tab lifetime.
 */

import { useState, useEffect, useCallback } from 'react';
import { sessionService, GuestSession } from '../services/session.service';

interface UseGuestSessionResult {
  session: GuestSession | null;
  isLoading: boolean;
  error: string | null;
  retry: () => void;
}

export function useGuestSession(): UseGuestSessionResult {
  const [session, setSession] = useState<GuestSession | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initSession = useCallback(async () => {
    // If we already have a token stored, reconstruct session state without
    // creating a new one on the backend.
    const existingToken = sessionService.getToken();
    if (existingToken) {
      // We don't have sessionId from storage alone, but token contains it.
      // Create a minimal session object — the token is what the API needs.
      setSession({
        token: existingToken,
        sessionId: 'existing',
        expiresAt: '',
        tokenType: 'bearer',
      });
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const newSession = await sessionService.createSession();
      setSession(newSession);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to initialize session.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  return { session, isLoading, error, retry: initSession };
}
