/**
 * PrintBar — Session Service
 *
 * POST /api/v1/sessions      → create guest session (returns JWT)
 * DELETE /api/v1/sessions/me → terminate session
 *
 * Token is stored in sessionStorage so it survives page reloads
 * within the same browser tab but not across tabs or after close.
 */

import { apiFetch, GUEST_TOKEN_KEY, setGuestToken } from '../lib/api';

export interface GuestSession {
  sessionId: string;
  token: string;
  accessToken?: string;
  expiresAt: string;
  tokenType: string;
}

export const sessionService = {
  /**
   * Creates a new anonymous guest session on the backend and
   * stores the returned JWT in sessionStorage.
   */
  async createSession(): Promise<GuestSession> {
    const raw = await apiFetch<any>({
      method: 'POST',
      url: '/sessions',
    });

    const tokenString = raw.accessToken || raw.token || '';
    const session: GuestSession = {
      sessionId: raw.sessionId,
      token: tokenString,
      accessToken: tokenString,
      expiresAt: raw.expiresAt || '',
      tokenType: 'bearer',
    };

    setGuestToken(tokenString);
    return session;
  },

  /**
   * Tells the backend the session is over and clears the stored token.
   * Since sessions are stateless JWTs, this is primarily a client-side logout.
   */
  async terminateSession(): Promise<void> {
    try {
      await apiFetch<{ message: string }>({
        method: 'DELETE',
        url: '/sessions/me',
      });
    } finally {
      sessionStorage.removeItem(GUEST_TOKEN_KEY);
    }
  },

  /** Returns true if a guest token is currently stored. */
  hasActiveSession(): boolean {
    const token = sessionStorage.getItem(GUEST_TOKEN_KEY);
    return !!token && token !== 'undefined' && token !== 'null';
  },

  /** Returns the raw token string or null. */
  getToken(): string | null {
    const token = sessionStorage.getItem(GUEST_TOKEN_KEY);
    if (!token || token === 'undefined' || token === 'null') return null;
    return token;
  },
};
